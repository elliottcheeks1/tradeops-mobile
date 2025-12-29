import sqlite3
import json
import random
from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="TradeOps Pro")
templates = Jinja2Templates(directory="templates")

# Use [[ ]] for Jinja so Vue can keep {{ }}
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

# ---------- DB HELPERS ----------

def query_db(query, args=(), one: bool = False):
    """
    For SELECTs only – returns list[dict] or single dict if one=True.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]

def execute_db(query, args=()):
    """
    For INSERT/UPDATE/DELETE – commits the change.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 1. CORE DATA (Dropdowns)

@app.get("/api/init-data")
async def get_init_data():
    customers = query_db(
        "SELECT id, name, type, address, email, phone FROM customers ORDER BY name"
    )
    catalog = query_db(
        "SELECT id, name, price, type FROM catalog ORDER BY type DESC, name"
    )
    return {"customers": customers, "catalog": catalog}

# 2. DASHBOARD & LISTS

@app.get("/api/dashboard")
async def get_dashboard():
    quotes = query_db("SELECT * FROM quotes")
    total_rev = sum(q.get("total", 0) for q in quotes) if quotes else 0.0
    pending = len([q for q in quotes if q.get("status") in ("Draft", "Quote", "Estimate")])
    active_jobs = len([q for q in quotes if q.get("status") in ("Scheduled", "In Progress")])
    avg_ticket = (total_rev / len(quotes)) if quotes else 0.0

    recent = query_db(
        """
        SELECT q.id,
               c.name,
               q.total,
               q.status,
               q.created_at
        FROM quotes q
        JOIN customers c ON q.customer_id = c.id
        ORDER BY q.created_at DESC
        LIMIT 5
        """
    )

    # Today's schedule (safe if columns don't exist yet)
    try:
        schedule = query_db(
            """
            SELECT q.id,
                   c.name,
                   q.total,
                   q.status,
                   q.tech,
                   q.scheduled_date
            FROM quotes q
            JOIN customers c ON q.customer_id = c.id
            WHERE date(q.scheduled_date) = date('now')
            ORDER BY q.scheduled_date ASC
            """
        )
    except sqlite3.OperationalError:
        # If scheduled_date/tech not in the DB yet, just return an empty list
        schedule = []

    return {
        "revenue": total_rev,
        "pending": pending,
        "active_jobs": active_jobs,
        "avg_ticket": avg_ticket,
        "recent": recent,
        "schedule": schedule,
    }

@app.get("/api/quotes")
async def get_quotes():
    return query_db(
        """
        SELECT q.id,
               c.name AS customer_name,
               q.status,
               q.total,
               q.created_at
        FROM quotes q
        JOIN customers c ON q.customer_id = c.id
        ORDER BY q.created_at DESC
        """
    )

@app.get("/api/accounts")
async def get_accounts():
    return query_db("SELECT * FROM customers ORDER BY name")

# 3. ACTIONS

@app.post("/api/customers")
async def create_customer(cust: CustomerIn):
    """
    Create a new customer / account.
    (Bug fix: now uses execute_db so the INSERT is committed.)
    """
    new_id = f"C-{random.randint(10000, 99999)}"
    execute_db(
        """
        INSERT INTO customers (id, name, type, email, phone, address, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            cust.name,
            cust.type,
            cust.email,
            cust.phone,
            cust.address,
            datetime.now().isoformat(),
        ),
    )
    return {"status": "success", "id": new_id}

@app.post("/api/quotes")
async def save_quote(quote: QuoteIn):
    """
    Save a quote created in the Builder.
    """
    new_id = f"Q-{random.randint(1000, 9999)}"
    execute_db(
        """
        INSERT INTO quotes
        (id, customer_id, status, created_at, items_json, total, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            quote.customer_id,
            "Draft",
            date.today().isoformat(),
            json.dumps([i.dict() for i in quote.items]),
            quote.total,
            quote.notes,
        ),
    )
    return {"status": "success", "id": new_id}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=True)
