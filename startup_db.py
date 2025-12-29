import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import uuid

DB_NAME = "tradeops_v2.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Customers Table
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        address TEXT,
        phone TEXT,
        email TEXT
    )''')
    
    # 2. Parts Catalog (Standard items)
    c.execute('''CREATE TABLE IF NOT EXISTS parts_catalog (
        part_id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        cost REAL, -- Hidden from tech
        retail_price REAL
    )''')
    
    # 3. Quotes Header
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        quote_id TEXT,
        version INTEGER,
        customer_id TEXT, -- Linked to customers
        job_type TEXT,
        estimator TEXT,
        status TEXT,
        created_at TEXT,
        last_contact_at TEXT,
        next_followup_date TEXT,
        followup_status TEXT,
        total_price REAL,
        total_cost REAL,
        margin_percent REAL,
        PRIMARY KEY (quote_id, version)
    )''')
    
    # 4. Quote Items
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

    # --- SEED DATA ---
    
    # Seed Customers
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        customers = [
            ("C1", "Walmart Supercenter", "8800 Retail Pkwy", "555-0101", "mgr@walmart.com"),
            ("C2", "Mrs. Robinson", "123 Graduate Ln", "555-0999", "mrs.robinson@gmail.com"),
            ("C3", "Burger King #42", "450 Whopper Way", "555-0200", "bk42@franchise.com")
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # Seed Parts Catalog
    c.execute("SELECT count(*) FROM parts_catalog")
    if c.fetchone()[0] == 0:
        parts = [
            ("P001", "Capacitor 45/5 MFD", "Dual run capacitor", 12.50, 85.00),
            ("P002", "Contactor 2 Pole 30A", "Standard AC contactor", 18.00, 125.00),
            ("P003", "R410a Refrigerant (lb)", "Price per pound", 15.00, 85.00),
            ("P004", "Hard Start Kit", "Compressor saver", 35.00, 250.00),
            ("P005", "Limit Switch", "Generic furnace limit", 22.00, 145.00),
        ]
        c.executemany("INSERT INTO parts_catalog VALUES (?,?,?,?,?)", parts)

    conn.commit()
    conn.close()

# --- DATA ACCESS ---

def get_customers():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM customers", conn)
    conn.close()
    return df

def add_customer(name, address, phone, email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c_id = str(uuid.uuid4())[:8]
    c.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (c_id, name, address, phone, email))
    conn.commit()
    conn.close()
    return c_id

def get_parts():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM parts_catalog", conn)
    conn.close()
    return df

def save_quote_v2(customer_id, job_type, estimator, items):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    q_id = str(uuid.uuid4())[:8]
    
    # Calculate hidden totals
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0
    
    now = datetime.now().strftime("%Y-%m-%d")
    next_fup = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    c.execute('''INSERT INTO quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (q_id, 1, customer_id, job_type, estimator, "Open", now, now, next_fup, "Needs Call", total_price, total_cost, margin))
    
    for i in items:
        c.execute("INSERT INTO quote_items (quote_id, version, item_name, item_type, unit_cost, unit_price, quantity) VALUES (?,?,?,?,?,?,?)",
                  (q_id, 1, i['name'], i['type'], i['cost'], i['price'], i['qty']))
        
    conn.commit()
    conn.close()
    return q_id

def get_office_dashboard_data():
    conn = sqlite3.connect(DB_NAME)
    # Join Customers to get names
    query = """
    SELECT q.quote_id, c.name as client_name, q.total_price, q.total_cost, q.margin_percent, q.status, q.estimator
    FROM quotes q
    LEFT JOIN customers c ON q.customer_id = c.customer_id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

if __name__ == "__main__":
    init_db()
    print("Database Updated with Parts & Customers.")