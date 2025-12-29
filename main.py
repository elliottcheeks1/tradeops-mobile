import sqlite3
import json
import random
from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# --- CONFIG ---
app = FastAPI(title="TradeOps Pro")
templates = Jinja2Templates(directory="templates")
DB_FILE = "tradeops_ultimate_v2.db"

# --- DATA MODELS ---
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

# --- DATABASE HELPERS ---
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (dict(rv[0]) if rv else None) if one else [dict(row) for row in rv]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create Tables
    c.execute('''CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, type TEXT, notes TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL, sku TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT, items_json TEXT, total REAL, notes TEXT)''')

    # Seed Data (Only if empty)
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        print("Seeding Rich Dummy Data...")
        customers = [
            ("C-1", "Burger King #402", "123 Whopper Ln", "bk402@franchise.com", "555-0101", "Commercial", "Gate code: 1234", datetime.now().isoformat()),
            ("C-2", "Marriott Downtown", "400 Congress Ave", "mgr@marriott.com", "555-0102", "Commercial", "Check in at security", datetime.now().isoformat()),
            ("C-3", "John Doe", "88 Maple Dr", "john@gmail.com", "555-0199", "Residential", "Large dog in backyard", datetime.now().isoformat()),
            ("C-4", "Whole Foods Market", "500 Lamar Blvd", "facilities@wholefoods.com", "555-0200", "Commercial", "Loading dock delivery only", datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
        
        catalog = [
            ("P-1", "Trane 5-Ton Condenser", "Part", 1800.0, 4200.0, "HVAC-TR-05"),
            ("P-2", "Evaporator Coil (Commercial)", "Part", 650.0, 1450.0, "HVAC-COIL-02"),
            ("P-3", "Ecobee Smart Thermostat", "Part", 140.0, 385.0, "ELEC-TH-01"),
            ("L-1", "Master Technician Labor", "Labor", 65.0, 185.0, "LAB-MST"),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0, "LAB-APP"),
            ("F-1", "Emergency Service Fee", "Fee", 0.0, 250.0, "FEE-EMG"),
            ("F-2", "Permit & Inspection Fee", "Fee", 0.0, 150.0, "FEE-PMT"),
        ]
        c.executemany("INSERT INTO catalog VALUES (?,?,?,?,?,?)", catalog)
        
    conn.commit()
    conn.close()

init_db()

# --- API ROUTES ---

# 1. Page Load
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 2. Data Fetching
@app.get("/api/init-data")
async def get_init_data():
    """Fetches everything needed for the frontend on load"""
    customers = query_db("SELECT id, name, type FROM customers ORDER BY name")
    catalog = query_db("SELECT id, name, price, type FROM catalog ORDER BY type DESC, name")
    return {"customers": customers, "catalog": catalog}

# 3. Actions
@app.post("/api/customers")
async def create_customer(cust: CustomerIn):
    new_id = f"C-{random.randint(10000, 99999)}"
    query_db(
        "INSERT INTO customers (id, name, type, email, phone, address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (new_id, cust.name, cust.type, cust.email, cust.phone, cust.address, datetime.now().isoformat())
    )
    # Return the new list so the dropdown updates immediately
    all_customers = query_db("SELECT id, name, type FROM customers ORDER BY name")
    return {"status": "success", "customers": all_customers}

@app.post("/api/quotes")
async def save_quote(quote: QuoteIn):
    new_id = f"Q-{random.randint(1000, 9999)}"
    query_db(
        "INSERT INTO quotes (id, customer_id, status, created_at, items_json, total, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (new_id, quote.customer_id, "Draft", date.today().isoformat(), json.dumps([i.dict() for i in quote.items]), quote.total, quote.notes)
    )
    return {"status": "success", "id": new_id}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
