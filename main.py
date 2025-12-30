import sqlite3
import json
import random
import os
from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="TradeOps Pro")

templates = Jinja2Templates(directory="templates")
templates.env.variable_start_string = '[['
templates.env.variable_end_string = ']]'

DB_FILE = "tradeops_v3.db"

# ---------- MODELS ----------
class LoginRequest(BaseModel):
    username: str
    password: str

class CustomerIn(BaseModel):
    name: str
    type: str = "Commercial"
    email: Optional[str] = ""
    phone: Optional[str] = ""
    address: Optional[str] = ""

class QuoteItem(BaseModel):
    id: str
    name: str
    qty: int
    price: float

class QuoteIn(BaseModel):
    customer_id: str
    items: List[QuoteItem]
    total: float
    notes: Optional[str] = ""

class StatusUpdate(BaseModel):
    status: str

# ---------- DB INIT ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # 1. Customers
    cur.execute('''CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY, name TEXT, type TEXT, address TEXT, email TEXT, phone TEXT, created_at TEXT)''')

    # 2. Quotes
    cur.execute('''CREATE TABLE IF NOT EXISTS quotes (
        id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT, items_json TEXT, total REAL, notes TEXT)''')

    # 3. Catalog
    cur.execute('''CREATE TABLE IF NOT EXISTS catalog (
        id TEXT PRIMARY KEY, name TEXT, type TEXT, price REAL)''')

    # 4. Users (New for Roles)
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, full_name TEXT)''')
    
    # Seed Data
    cur.execute('SELECT count(*) FROM catalog')
    if cur.fetchone()[0] == 0:
        # Seed Catalog
        cur.executemany('INSERT INTO catalog VALUES (?,?,?,?)', [
            ("P-101", "16 SEER Condenser", "Part", 2800.00),
            ("L-001", "Master Labor (Hr)", "Labor", 185.00)
        ])
        # Seed Users (admin/admin and tech/tech)
        cur.executemany('INSERT INTO users VALUES (?,?,?,?)', [
            ("admin", "admin", "admin", "Elliott Cheeks"),
            ("tech", "tech", "tech", "Sarah Jenkins")
        ])
        conn.commit()
    conn.close()

init_db()

# ---------- HELPERS ----------
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (dict(rows[0]) if rows else None) if one else [dict(r) for r in rows]

def execute_db(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute(query, args)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/login")
async def login(creds: LoginRequest):
    user = query_db("SELECT * FROM users WHERE username = ? AND password = ?", (creds.username, creds.password), one=True)
    if user:
        return {"status": "success", "user": user}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/init-data")
async def get_init_data():
    return {
        "customers": query_db("SELECT * FROM customers ORDER BY name"),
        "catalog": query_db("SELECT * FROM catalog ORDER BY type DESC, name")
    }

@app.get("/api/dashboard")
async def get_dashboard():
    quotes = query_db("SELECT * FROM quotes")
    total_rev = sum(q['total'] for q in quotes) if quotes else 0
    recent = query_db("""
        SELECT q.id, c.name, q.total, q.status, q.created_at 
        FROM quotes q LEFT JOIN customers c ON q.customer_id = c.id 
        ORDER BY q.created_at DESC LIMIT 5
    """)
    return {
        "revenue": total_rev,
        "pending": len([q for q in quotes if q['status'] == 'Draft']),
        "recent": recent
    }

@app.get("/api/quotes")
async def get_quotes():
    return query_db("""
        SELECT q.id, c.name as customer_name, q.status, q.total, q.created_at 
        FROM quotes q LEFT JOIN customers c ON q.customer_id = c.id 
        ORDER BY q.created_at DESC
    """)

@app.post("/api/customers")
async def create_customer(cust: CustomerIn):
    new_id = f"C-{random.randint(10000, 99999)}"
    execute_db("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
               (new_id, cust.name, cust.type, cust.address, cust.email, cust.phone, datetime.now().isoformat()))
    return {"status": "success", "id": new_id}

@app.put("/api/customers/{id}")
async def update_customer(id: str, cust: CustomerIn):
    execute_db("UPDATE customers SET name=?, type=?, address=?, email=?, phone=? WHERE id=?",
               (cust.name, cust.type, cust.address, cust.email, cust.phone, id))
    return {"status": "success"}

@app.post("/api/quotes")
async def save_quote(quote: QuoteIn):
    new_id = f"Q-{random.randint(1000, 9999)}"
    items_json = json.dumps([i.dict() for i in quote.items])
    execute_db("INSERT INTO quotes VALUES (?, ?, ?, ?, ?, ?, ?)",
               (new_id, quote.customer_id, "Draft", date.today().isoformat(), items_json, quote.total, quote.notes))
    return {"status": "success", "id": new_id}

@app.put("/api/quotes/{id}/status")
async def update_quote_status(id: str, update: StatusUpdate):
    execute_db("UPDATE quotes SET status=? WHERE id=?", (update.status, id))
    return {"status": "updated"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
