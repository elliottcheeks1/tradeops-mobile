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

# Setup Templates (Assumes index.html is in a 'templates' folder)
# If index.html is in the same folder, change directory="."
templates = Jinja2Templates(directory="templates")
templates.env.variable_start_string = '[['
templates.env.variable_end_string = ']]'

DB_FILE = "tradeops_ultimate_v2.db"

# ---------- MODELS ----------
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

# ---------- DB INIT & HELPERS ----------
def init_db():
    """Creates the necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # Create Customers Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            address TEXT,
            email TEXT,
            phone TEXT,
            created_at TEXT
        )
    ''')

    # Create Quotes Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS quotes (
            id TEXT PRIMARY KEY,
            customer_id TEXT,
            status TEXT,
            created_at TEXT,
            items_json TEXT,
            total REAL,
            notes TEXT
        )
    ''')

    # Create Catalog Table (and seed it if empty)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS catalog (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            price REAL
        )
    ''')
    
    # Seed Catalog if empty
    cur.execute('SELECT count(*) FROM catalog')
    if cur.fetchone()[0] == 0:
        seed_items = [
            ("P-101", "16 SEER Condenser", "Part", 2800.00),
            ("P-102", "Smart Thermostat", "Part", 250.00),
            ("L-001", "Master Labor (Hr)", "Labor", 185.00),
            ("L-002", "Helper Labor (Hr)", "Labor", 95.00),
            ("S-500", "Freon Recharge", "Service", 300.00)
        ]
        cur.executemany('INSERT INTO catalog VALUES (?,?,?,?)', seed_items)

    conn.commit()
    conn.close()

# Run DB Init on startup
init_db()

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

@app.get("/api/init-data")
async def get_init_data():
    customers = query_db("SELECT * FROM customers ORDER BY name")
    catalog = query_db("SELECT * FROM catalog ORDER BY type DESC, name")
    return {"customers": customers, "catalog": catalog}

@app.get("/api/dashboard")
async def get_dashboard():
    quotes = query_db("SELECT * FROM quotes")
    total_rev = sum(q['total'] for q in quotes) if quotes else 0
    
    # Get Recent 5
    recent = query_db("""
        SELECT q.id, c.name, q.total, q.status, q.created_at 
        FROM quotes q 
        LEFT JOIN customers c ON q.customer_id = c.id 
        ORDER BY q.created_at DESC LIMIT 5
    """)
    
    return {
        "revenue": total_rev,
        "active_jobs": 0, # Placeholder
        "pending": len(quotes),
        "avg_ticket": (total_rev / len(quotes)) if quotes else 0,
        "recent": recent,
        "schedule": []
    }

@app.get("/api/quotes")
async def get_quotes():
    return query_db("""
        SELECT q.id, c.name as customer_name, q.status, q.total, q.created_at 
        FROM quotes q 
        LEFT JOIN customers c ON q.customer_id = c.id 
        ORDER BY q.created_at DESC
    """)

@app.post("/api/customers")
async def create_customer(cust: CustomerIn):
    try:
        new_id = f"C-{random.randint(10000, 99999)}"
        execute_db(
            "INSERT INTO customers (id, name, type, email, phone, address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id, cust.name, cust.type, cust.email, cust.phone, cust.address, datetime.now().isoformat())
        )
        return {"status": "success", "id": new_id}
    except Exception as e:
        print(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quotes")
async def save_quote(quote: QuoteIn):
    try:
        new_id = f"Q-{random.randint(1000, 9999)}"
        # Convert items objects to dicts for JSON serialization
        items_json = json.dumps([i.dict() for i in quote.items])
        
        execute_db(
            "INSERT INTO quotes (id, customer_id, status, created_at, items_json, total, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id, quote.customer_id, "Draft", date.today().isoformat(), items_json, quote.total, quote.notes)
        )
        return {"status": "success", "id": new_id}
    except Exception as e:
        print(f"Error saving quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
