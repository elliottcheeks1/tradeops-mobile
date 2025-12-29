import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import uuid

DB_NAME = "tradeops_v3.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        address TEXT,
        phone TEXT,
        email TEXT
    )''')
    
    # 2. Catalogs (Parts & Labor)
    c.execute('''CREATE TABLE IF NOT EXISTS parts_catalog (
        part_id TEXT PRIMARY KEY,
        name TEXT,
        cost REAL, 
        retail_price REAL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS labor_rates (
        role TEXT PRIMARY KEY,
        base_cost REAL,
        bill_rate REAL
    )''')
    
    # 3. Quotes Header (Lifecycle & Versioning)
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        quote_id TEXT,
        version INTEGER,
        customer_id TEXT,
        job_type TEXT,
        estimator TEXT,
        status TEXT, -- Open, Won, Lost
        created_at TEXT,
        last_contact_at TEXT,
        next_followup_date TEXT,
        followup_status TEXT, 
        total_price REAL,
        total_cost REAL,
        margin_percent REAL,
        PRIMARY KEY (quote_id, version)
    )''')
    
    # 4. Quote Line Items
    c.execute('''CREATE TABLE IF NOT EXISTS quote_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id TEXT,
        version INTEGER,
        item_name TEXT,
        item_type TEXT, 
        unit_cost REAL,
        unit_price REAL,
        quantity REAL
    )''')

    # --- SEEDING ---
    # Seed Labor (Gap B2)
    c.execute("SELECT count(*) FROM labor_rates")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO labor_rates VALUES (?,?,?)", [
            ("Apprentice", 20.0, 65.0),
            ("Journeyman", 35.0, 95.0),
            ("Master Tech", 55.0, 150.0)
        ])

    # Seed Parts
    c.execute("SELECT count(*) FROM parts_catalog")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO parts_catalog VALUES (?,?,?,?)", [
            ("P1", "Capacitor 45/5", 12.0, 85.0),
            ("P2", "Contactor 30A", 18.0, 125.0),
            ("P3", "R410a (lb)", 15.0, 85.0)
        ])
        
    # Seed Customers
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
            ("C1", "Walmart", "8800 Retail Pkwy", "555-0101", "mgr@walmart.com"),
            ("C2", "Mrs. Jones", "12 Oak St", "555-0999", "jones@gmail.com")
        ])

    conn.commit()
    conn.close()

# --- DATA ACCESS ---

def get_customers():
    return pd.read_sql("SELECT * FROM customers", sqlite3.connect(DB_NAME))

def get_parts():
    return pd.read_sql("SELECT * FROM parts_catalog", sqlite3.connect(DB_NAME))

def get_labor():
    return pd.read_sql("SELECT * FROM labor_rates", sqlite3.connect(DB_NAME))

def add_customer(name, addr, phone):
    conn = sqlite3.connect(DB_NAME)
    cid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (cid, name, addr, phone, ""))
    conn.commit()
    conn.close()
    return cid

def save_quote(cust_id, job_type, estimator, items):
    conn = sqlite3.connect(DB_NAME)
    qid = str(uuid.uuid4())[:8]
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d")
    next_fup = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d") # Default 3 day follow-up (Gap B1)
    
    conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                 (qid, 1, cust_id, job_type, estimator, "Open", now, now, next_fup, "Needs Call", total_price, total_cost, margin))
    
    for i in items:
        conn.execute("INSERT INTO quote_items (quote_id, version, item_name, item_type, unit_cost, unit_price, quantity) VALUES (?,?,?,?,?,?,?)",
                     (qid, 1, i['name'], i['type'], i['cost'], i['price'], i['qty']))
    conn.commit()
    conn.close()
    return qid

def get_followup_queue():
    query = """
    SELECT q.quote_id, c.name, q.total_price, q.next_followup_date, q.followup_status, q.estimator
    FROM quotes q JOIN customers c ON q.customer_id = c.customer_id
    WHERE q.status = 'Open' ORDER BY q.next_followup_date ASC
    """
    return pd.read_sql(query, sqlite3.connect(DB_NAME))

def get_analytics():
    # Gap D: Close rates and time series
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM quotes", conn)
    conn.close()
    return df

if __name__ == "__main__":
    init_db()
    print("V3 Database Initialized")