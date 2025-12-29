import sqlite3
import pandas as pd
from datetime import datetime
import uuid

DB_NAME = "tradeops_v4.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        street TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        phone TEXT,
        email TEXT
    )''')
    
    # 2. Catalogs
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
    
    # 3. Quotes Header
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        quote_id TEXT PRIMARY KEY,
        customer_id TEXT,
        job_type TEXT,
        estimator TEXT,
        status TEXT, 
        created_at TEXT,
        last_modified_at TEXT,
        next_followup_date TEXT,
        followup_status TEXT, 
        total_price REAL,
        total_cost REAL,
        margin_percent REAL
    )''')
    
    # 4. Quote Items
    c.execute('''CREATE TABLE IF NOT EXISTS quote_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id TEXT,
        item_name TEXT,
        item_type TEXT, 
        unit_cost REAL,
        unit_price REAL,
        quantity REAL
    )''')

    # Seed Data
    c.execute("SELECT count(*) FROM labor_rates")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO labor_rates VALUES (?,?,?)", [
            ("Apprentice", 20.0, 65.0),
            ("Journeyman", 35.0, 95.0),
            ("Master Tech", 55.0, 150.0)
        ])
        c.executemany("INSERT INTO parts_catalog VALUES (?,?,?,?)", [
            ("P1", "Capacitor 45/5", 12.0, 85.0),
            ("P2", "Contactor 30A", 18.0, 125.0),
            ("P3", "R410a (lb)", 15.0, 85.0)
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

def add_customer(name, street, city, state, zip_code, phone):
    conn = sqlite3.connect(DB_NAME)
    cid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", 
                 (cid, name, street, city, state, zip_code, phone, ""))
    conn.commit()
    conn.close()
    return cid

# --- QUOTE ACTIONS ---

def save_new_quote(cust_id, job_type, estimator, items):
    conn = sqlite3.connect(DB_NAME)
    qid = str(uuid.uuid4())[:8]
    
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d")
    
    conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", 
                 (qid, cust_id, job_type, estimator, "Open", now, now, now, "Needs Call", total_price, total_cost, margin))
    
    for i in items:
        conn.execute("INSERT INTO quote_items (quote_id, item_name, item_type, unit_cost, unit_price, quantity) VALUES (?,?,?,?,?,?)",
                     (qid, i['name'], i['type'], i['cost'], i['price'], i['qty']))
    
    conn.commit()
    conn.close()
    return qid

def update_existing_quote(quote_id, cust_id, job_type, estimator, items):
    conn = sqlite3.connect(DB_NAME)
    
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d")

    conn.execute("""
        UPDATE quotes 
        SET total_price=?, total_cost=?, margin_percent=?, last_modified_at=?, job_type=?, estimator=?
        WHERE quote_id=?
    """, (total_price, total_cost, margin, now, job_type, estimator, quote_id))

    conn.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))

    for i in items:
        conn.execute("INSERT INTO quote_items (quote_id, item_name, item_type, unit_cost, unit_price, quantity) VALUES (?,?,?,?,?,?)",
                     (quote_id, i['name'], i['type'], i['cost'], i['price'], i['qty']))
                     
    conn.commit()
    conn.close()
    return quote_id

# --- HISTORY & CRM ---

def get_tech_history(estimator_name=None):
    conn = sqlite3.connect(DB_NAME)
    query = """
    SELECT q.quote_id, c.name, q.total_price, q.status, q.created_at, q.last_modified_at, q.estimator
    FROM quotes q JOIN customers c ON q.customer_id = c.customer_id
    """
    if estimator_name:
        query += f" WHERE q.estimator LIKE '%{estimator_name}%'"
        
    query += " ORDER BY q.last_modified_at DESC"
    return pd.read_sql(query, conn)

def get_followup_queue():
    # Only show open quotes that need attention
    query = """
    SELECT q.quote_id, c.name, c.phone, q.total_price, q.next_followup_date, q.followup_status, q.estimator
    FROM quotes q JOIN customers c ON q.customer_id = c.customer_id
    WHERE q.status = 'Open' 
    ORDER BY q.next_followup_date ASC
    """
    return pd.read_sql(query, sqlite3.connect(DB_NAME))

def log_interaction(quote_id, new_status, next_date):
    conn = sqlite3.connect(DB_NAME)
    now = datetime.now().strftime("%Y-%m-%d")
    conn.execute("UPDATE quotes SET followup_status = ?, next_followup_date = ?, last_contact_at = ? WHERE quote_id = ?", 
                 (new_status, next_date, now, quote_id))
    conn.commit()
    conn.close()

def get_quote_details(quote_id):
    conn = sqlite3.connect(DB_NAME)
    header = pd.read_sql(f"SELECT * FROM quotes WHERE quote_id='{quote_id}'", conn).iloc[0]
    items = pd.read_sql(f"SELECT * FROM quote_items WHERE quote_id='{quote_id}'", conn)
    conn.close()
    return header, items