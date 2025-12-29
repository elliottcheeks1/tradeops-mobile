import os
import sqlalchemy
from sqlalchemy import create_engine, text
import pandas as pd
import uuid
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# Check if we are in the cloud (Render) or local
db_url = os.environ.get("DATABASE_URL")

# Fix for Render/Neon compatibility (postgres:// -> postgresql://)
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# If no cloud DB found, fallback to local file
if not db_url:
    db_url = "sqlite:///tradeops_v2.db"

ENGINE = create_engine(db_url)

def run_query(query, params=None):
    """Executes SQL safely on both SQLite and Postgres"""
    with ENGINE.connect() as conn:
        if params:
            # SQLAlchemy text() requires parameters to be passed as a dictionary
            result = conn.execute(text(query), params)
        else:
            result = conn.execute(text(query))
        
        # If SELECT, return DataFrame
        if query.strip().upper().startswith("SELECT"):
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        
        # If INSERT/UPDATE, commit logic is handled by the connection context usually, 
        # but explicit commit ensures data is saved.
        conn.commit()

def init_db():
    # Create Tables (Compatible with both DB types)
    run_query('''CREATE TABLE IF NOT EXISTS labor_rates (
        role VARCHAR(50) PRIMARY KEY,
        base_cost FLOAT,
        bill_rate FLOAT
    )''')
    
    run_query('''CREATE TABLE IF NOT EXISTS quotes (
        quote_id VARCHAR(50),
        version INTEGER,
        client_name VARCHAR(100),
        job_type VARCHAR(50),
        estimator VARCHAR(100),
        status VARCHAR(20),
        created_at VARCHAR(20),
        last_contact_at VARCHAR(20),
        next_followup_date VARCHAR(20),
        followup_status VARCHAR(50),
        total_price FLOAT,
        total_cost FLOAT,
        margin_percent FLOAT,
        PRIMARY KEY (quote_id, version)
    )''')
    
    run_query('''CREATE TABLE IF NOT EXISTS quote_items (
        id SERIAL, 
        quote_id VARCHAR(50),
        version INTEGER,
        item_name VARCHAR(100),
        item_type VARCHAR(50),
        unit_cost FLOAT,
        unit_price FLOAT,
        quantity FLOAT
    )''')

    # Seed Data
    try:
        df = run_query("SELECT count(*) as cnt FROM labor_rates")
        # Handle different count return types between DBs
        count = df.iloc[0]['cnt']
        if count == 0:
            rates = [
                {"role": "Apprentice", "base": 20.0, "bill": 65.0},
                {"role": "Journeyman", "base": 35.0, "bill": 95.0},
                {"role": "Master Electrician", "base": 55.0, "bill": 150.0}
            ]
            for r in rates:
                run_query("INSERT INTO labor_rates (role, base_cost, bill_rate) VALUES (:role, :base, :bill)",
                          {"role": r['role'], "base": r['base'], "bill": r['bill']})
            print("Default Labor Rates Seeded.")
    except Exception as e:
        print(f"DB Init Warning: {e}")

# --- DATA FUNCTIONS ---
def get_labor_rates():
    return run_query("SELECT * FROM labor_rates")

def save_quote(client, job_type, estimator, items):
    q_id = str(uuid.uuid4())[:8]
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d")
    next_fup = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    run_query("""
        INSERT INTO quotes (quote_id, version, client_name, job_type, estimator, status, created_at, last_contact_at, next_followup_date, followup_status, total_price, total_cost, margin_percent)
        VALUES (:id, 1, :cl, :jt, :est, 'Open', :now, :now, :nxt, 'Needs Call', :tp, :tc, :mp)
    """, {"id": q_id, "cl": client, "jt": job_type, "est": estimator, "now": now, "nxt": next_fup, "tp": total_price, "tc": total_cost, "mp": margin})
    
    for i in items:
        run_query("""
            INSERT INTO quote_items (quote_id, version, item_name, item_type, unit_cost, unit_price, quantity)
            VALUES (:id, 1, :name, :type, :cost, :price, :qty)
        """, {"id": q_id, "name": i['name'], "type": i['type'], "cost": i['cost'], "price": i['price'], "qty": i['qty']})
    return q_id

def get_followup_queue():
    today = datetime.now().strftime("%Y-%m-%d")
    return run_query(f"SELECT * FROM quotes WHERE status = 'Open' AND next_followup_date <= '{today}' ORDER BY next_followup_date ASC")

def update_followup(quote_id, version, new_status, next_date_str):
    now = datetime.now().strftime("%Y-%m-%d")
    run_query("""
        UPDATE quotes 
        SET followup_status = :stat, next_followup_date = :nxt, last_contact_at = :now
        WHERE quote_id = :qid AND version = :ver
    """, {"stat": new_status, "nxt": next_date_str, "now": now, "qid": quote_id, "ver": version})