import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import sqlite3
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta
import uuid
import os
import re

# --- CONFIGURATION ---
DB_NAME = "tradeops_single_file_v1.db"
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])
app.title = "TradeOps V8 (All-in-One)"
server = app.server

# --- DATABASE ENGINE (Built-in) ---
def init_db():
    # NUCLEAR OPTION: Delete DB on every restart to force data seed
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create Tables
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY, name TEXT, street TEXT, city TEXT, state TEXT, zip TEXT, phone TEXT, email TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS parts_catalog (
        part_id TEXT PRIMARY KEY, name TEXT, cost REAL, retail_price REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS labor_rates (
        role TEXT PRIMARY KEY, base_cost REAL, bill_rate REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        quote_id TEXT PRIMARY KEY, customer_id TEXT, job_type TEXT, estimator TEXT, status TEXT, 
        created_at TEXT, last_modified_at TEXT, next_followup_date TEXT, followup_status TEXT, 
        total_price REAL, total_cost REAL, margin_percent REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quote_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, quote_id TEXT, item_name TEXT, item_type TEXT, 
        unit_cost REAL, unit_price REAL, quantity REAL
    )''')
    
    # Seed Data Immediately
    # 1. Labor
    c.executemany("INSERT INTO labor_rates VALUES (?,?,?)", [
        ("Apprentice", 20.0, 65.0),
        ("Journeyman Tech", 35.0, 95.0),
        ("Master Electrician", 55.0, 150.0),
        ("HVAC Lead", 45.0, 125.0)
    ])
    # 2. Parts
    c.executemany("INSERT INTO parts_catalog VALUES (?,?,?,?)", [
        ("P101", "Capacitor 45/5 MFD", 12.50, 85.00),
        ("P102", "Contactor 2-Pole 30A", 18.00, 125.00),
        ("P103", "R410a Refrigerant (lb)", 15.00, 95.00),
        ("P104", "Hard Start Kit", 35.00, 245.00),
        ("P201", "PVC Pipe 2 inch (10ft)", 8.00, 25.00),
        ("P301", "Breaker 20 Amp", 9.00, 35.00)
    ])
    # 3. Customers
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", [
        ("C001", "Walmart Supercenter", "8800 Retail Pkwy", "Dallas", "TX", "75001", "555-0101", "mgr@walmart.com"),
        ("C002", "Burger King", "450 Whopper Way", "Houston", "TX", "77002", "555-0200", "bk@loves.com"),
        ("C003", "Residential - Smith", "12 Maple Dr", "Austin", "TX", "78701", "555-9999", "smith@gmail.com")
    ])
    
    conn.commit()
    conn.close()

# Initialize immediately
init_db()

# --- DATA HELPERS ---
def get_df(query):
    return pd.read_sql(query, sqlite3.connect(DB_NAME))

def add_customer(name, street, city, state, zip_c, phone):
    conn = sqlite3.connect(DB_NAME)
    cid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", (cid, name, street, city, state, zip_c, phone, ""))
    conn.commit()
    conn.close()
    return cid

def save_quote(qid, cust_id, job_type, estimator, items, mode="new"):
    conn = sqlite3.connect(DB_NAME)
    now = datetime.now().strftime("%Y-%m-%d")
    total_cost = sum([i['cost'] * i['qty'] for i in items])
    total_price = sum([i['price'] * i['qty'] for i in items])
    margin = ((total_price - total_cost) / total_price * 100) if total_price > 0 else 0

    if mode == "new":
        qid = str(uuid.uuid4())[:8]
        conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", 
                     (qid, cust_id, job_type, estimator, "Open", now, now, now, "Needs Call", total_price, total_cost, margin))
    else:
        conn.execute("UPDATE quotes SET total_price=?, total_cost=?, margin_percent=?, last_modified_at=?, job_type=?, estimator=? WHERE quote_id=?", 
                     (total_price, total_cost, margin, now, job_type, estimator, qid))
        conn.execute("DELETE FROM quote_items WHERE quote_id=?", (qid,))

    for i in items:
        conn.execute("INSERT INTO quote_items (quote_id, item_name, item_type, unit_cost, unit_price, quantity) VALUES (?,?,?,?,?,?)",
                     (qid, i['name'], i['type'], i['cost'], i['price'], i['qty']))
    conn.commit()
    conn.close()
    return qid

def get_quote_detail(qid):
    conn = sqlite3.connect(DB_NAME)
    h = pd.read_sql(f"SELECT * FROM quotes WHERE quote_id='{qid}'", conn).iloc[0]
    i = pd.read_sql(f"SELECT * FROM quote_items WHERE quote_id='{qid}'", conn)
    c_name = pd.read_sql(f"SELECT name FROM customers WHERE customer_id='{h['customer_id']}'", conn).iloc[0]['name']
    conn.close()
    return h, i, c_name

def log_interaction(qid, status, date):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE quotes SET followup_status=?, next_followup_date=? WHERE quote_id=?", (status, date, qid))
    conn.commit()
    conn.close()

# --- PDF GENERATOR ---
def generate_pdf(qid, c_name, items, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "TradeOps Services", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "123 Main St, Texas City, TX | 555-0199", ln=True, align='C')
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Quote #: {qid}", ln=True)
    pdf.cell(0, 10, f"Customer: {c_name}", ln=True)
    pdf.cell(0, 10, f"Date: {date_str}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 10, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Price", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", size=12)
    for item in items:
        pdf.cell(100, 10, str(item['name']), 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(50, 10, f"${item['price']:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(130, 10, "Total Estimate:", 0, 0, 'R')
    pdf.cell(50, 10, f"${total:,.2f}", 0, 1, 'R')
    
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', c_name)
    filename = f"Quote_{clean_name}_{date_str}.pdf"
    pdf.output(filename)
    return filename

# --- LAYOUT ---
app.layout = html.Div([
    dcc.Store(id="cart-store", data=[]),
    dcc.Store(id="edit-mode", data={"mode": "new", "qid": None}),
    dcc.Download(id="download-pdf"),
    
    dbc.NavbarSimple(brand="TradeOps V8", color="dark", dark=True),
    
    dbc.Tabs([
        # TAB 1: FOLLOW UP
        dbc.Tab(label="Follow-Up", children=[
            dbc.Container([
                html.Br(),
                dbc.Button("↻ Refresh Queue", id="btn-refresh-fup", color="light", size="sm", className="mb-2"),
                dash_table.DataTable(id="fup-table", row_selectable="single", style_table={'overflowX': 'auto'}),
                dbc.Button("Log Interaction", id="btn-open-log", color="primary", className="w-100 mt-2", disabled=True),
                
                dbc.Modal([
                    dbc.ModalHeader("Log Call"),
                    dbc.ModalBody([
                        dbc.Select(id="log-status", options=[
                            {"label": "Needs Call", "value": "Needs Call"},
                            {"label": "Left VM", "value": "Left VM"},
                            {"label": "Won", "value": "Won"},
                            {"label": "Lost", "value": "Lost"},
                        ], value="Needs Call"),
                        html.Br(),
                        dcc.DatePickerSingle(id="log-date", date=(datetime.now()+timedelta(days=2)).date()),
                        html.Br(), html.Br(),
                        dbc.Button("Save", id="btn-save-log", color="success", className="w-100")
                    ])
                ], id="modal-log", is_open=False)
            ], fluid=True)
        ]),
        
        # TAB 2: HISTORY
        dbc.Tab(label="History", children=[
            dbc.Container([
                html.Br(),
                dbc.Row([
                    dbc.Col(dbc.Input(id="filter-est", placeholder="Filter Estimator..."), width=8),
                    dbc.Col(dbc.Button("Go", id="btn-filter", color="secondary", className="w-100"), width=4)
                ]),
                html.Br(),
                dash_table.DataTable(id="hist-table", row_selectable="single", style_table={'overflowX': 'auto'}),
                dbc.Row([
                    dbc.Col(dbc.Button("Edit", id="btn-edit", color="warning", className="w-100", disabled=True), width=6),
                    dbc.Col(dbc.Button("PDF", id="btn-pdf", color="info", className="w-100", disabled=True), width=6)
                ], className="mt-2")
            ], fluid=True)
        ]),
        
        # TAB 3: BUILDER
        dbc.Tab(label="Builder", id="tab-builder-id", children=[
            dbc.Container([
                html.Br(),
                dbc.Card([dbc.CardHeader("1. Customer"), dbc.CardBody([
                    dcc.Dropdown(id="dd-cust", placeholder="Select Customer"),
                    dbc.Button("New Customer", id="btn-new-cust", size="sm", color="light", className="w-100 mt-2"),
                    dbc.Input(id="est-name", placeholder="Estimator Name", className="mt-2"),
                    dbc.Select(id="job-type", options=[
                        {"label": "Service", "value": "Service"}, {"label": "Install", "value": "Install"}
                    ], placeholder="Job Type", className="mt-2"),
                    
                    dbc.Modal([
                        dbc.ModalHeader("New Customer"),
                        dbc.ModalBody([
                            dbc.Input(id="nc-name", placeholder="Name"),
                            dbc.Input(id="nc-st", placeholder="Street"),
                            dbc.Input(id="nc-city", placeholder="City"),
                            dbc.Input(id="nc-zip", placeholder="Zip"),
                            dbc.Input(id="nc-phone", placeholder="Phone"),
                            dbc.Button("Save", id="btn-save-nc", color="success", className="mt-2 w-100")
                        ])
                    ], id="modal-nc", is_open=False)
                ])]),
                html.Br(),
                dbc.Card([dbc.CardHeader("2. Items"), dbc.CardBody([
                    dbc.Tabs([
                        dbc.Tab(label="Parts", children=[
                            html.Br(), dcc.Dropdown(id="dd-parts", placeholder="Search Parts..."),
                            dbc.Input(id="in-qty", type="number", placeholder="Qty", value=1, className="mt-2"),
                            dbc.Button("Add Part", id="btn-add-part", color="secondary", className="w-100 mt-2")
                        ]),
                        dbc.Tab(label="Labor", children=[
                            html.Br(), dbc.Select(id="dd-labor", placeholder="Select Role..."),
                            dbc.Input(id="in-hrs", type="number", placeholder="Hours", className="mt-2"),
                            dbc.Button("Add Labor", id="btn-add-labor", color="secondary", className="w-100 mt-2")
                        ])
                    ])
                ])]),
                html.Br(),
                dbc.Card([dbc.CardHeader("3. Summary"), dbc.CardBody([
                    html.Div(id="cart-view", style={"maxHeight": "200px", "overflowY": "auto"}),
                    html.Hr(),
                    html.H3(id="cart-total", className="text-end"),
                    dbc.Button("Finalize Quote", id="btn-finalize", color="success", size="lg", className="w-100"),
                    html.Div(id="msg-save", className="text-center mt-2")
                ])])
            ], fluid=True)
        ])
    ], id="main-tabs")
])

# --- CALLBACKS ---

# 1. LOAD DROPDOWNS & TABLES
@app.callback(
    [Output("dd-cust", "options"), Output("dd-parts", "options"), Output("dd-labor", "options"),
     Output("fup-table", "data"), Output("hist-table", "data")],
    [Input("main-tabs", "active_tab"), Input("btn-refresh-fup", "n_clicks"), Input("btn-filter", "n_clicks")],
    [State("filter-est", "value")]
)
def refresh_data(tab, n_ref, n_fil, est_filter):
    # Fetch Dropdowns
    c = get_df("SELECT * FROM customers")
    p = get_df("SELECT * FROM parts_catalog")
    l = get_df("SELECT * FROM labor_rates")
    
    c_opts = [{"label": r['name'], "value": r['customer_id']} for _, r in c.iterrows()]
    p_opts = [{"label": f"{r['name']} (${r['retail_price']})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in p.iterrows()]
    l_opts = [{"label": f"{r['role']} (${r['bill_rate']}/hr)", "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}"} for _, r in l.iterrows()]
    
    # Fetch Tables
    fup = get_df("SELECT quote_id, total_price, followup_status, next_followup_date FROM quotes WHERE status='Open' ORDER BY next_followup_date")
    
    hist_q = "SELECT quote_id, estimator, total_price, status, last_modified_at FROM quotes"
    if est_filter:
        hist_q += f" WHERE estimator LIKE '%{est_filter}%'"
    hist_q += " ORDER BY last_modified_at DESC"
    hist = get_df(hist_q)
    
    return c_opts, p_opts, l_opts, fup.to_dict('records'), hist.to_dict('records')

# 2. CART LOGIC
@app.callback(
    [Output("cart-store", "data"), Output("cart-view", "children"), Output("cart-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks"), Input("edit-mode", "data")],
    [State("cart-store", "data"), State("dd-parts", "value"), State("in-qty", "value"),
     State("dd-labor", "value"), State("in-hrs", "value")]
)
def update_cart(b1, b2, edit_data, cart, p_val, qty, l_val, hrs):
    trig = ctx.triggered_id
    if trig == "edit-mode": return dash.no_update, dash.no_update, dash.no_update
    
    if trig == "btn-add-part" and p_val:
        pid, name, cost, price = p_val.split("|")
        cart.append({"name": name, "type": "Part", "cost": float(cost), "price": float(price), "qty": float(qty)})
    if trig == "btn-add-labor" and l_val:
        role, cost, rate = l_val.split("|")
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(cost), "price": float(rate), "qty": float(hrs)})
        
    items = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']:.2f}", className="float-end")], className="border-bottom p-1") for i in cart]
    total = sum([i['price']*i['qty'] for i in cart])
    return cart, items, f"${total:,.2f}"

# 3. SAVE QUOTE
@app.callback(
    Output("msg-save", "children"),
    Input("btn-finalize", "n_clicks"),
    [State("dd-cust", "value"), State("job-type", "value"), State("est-name", "value"),
     State("cart-store", "data"), State("edit-mode", "data")]
)
def finalize_quote(n, cust, jtype, est, cart, emode):
    if not n or not cart or not cust: return ""
    qid = save_quote(emode['qid'], cust, jtype, est, cart, emode['mode'])
    return f"Saved! ID: {qid}"

# 4. CUSTOMER MODAL
@app.callback(
    [Output("modal-nc", "is_open"), Output("dd-cust", "value")],
    [Input("btn-new-cust", "n_clicks"), Input("btn-save-nc", "n_clicks")],
    [State("modal-nc", "is_open"), State("nc-name", "value"), State("nc-st", "value"),
     State("nc-city", "value"), State("nc-zip", "value"), State("nc-phone", "value")]
)
def handle_nc(b1, b2, is_open, name, st, city, zip_c, ph):
    if ctx.triggered_id == "btn-new-cust": return True, dash.no_update
    if ctx.triggered_id == "btn-save-nc" and name:
        return False, add_customer(name, st, city, "TX", zip_c, ph)
    return is_open, dash.no_update

# 5. LOGGING
@app.callback(
    [Output("modal-log", "is_open"), Output("btn-open-log", "disabled")],
    [Input("btn-open-log", "n_clicks"), Input("btn-save-log", "n_clicks"), Input("fup-table", "selected_rows")],
    [State("modal-log", "is_open"), State("fup-table", "data"), State("log-status", "value"), State("log-date", "date")]
)
def handle_log(b1, b2, sel, is_open, data, status, date):
    trig = ctx.triggered_id
    if trig == "fup-table": return is_open, not bool(sel)
    if trig == "btn-open-log": return True, False
    if trig == "btn-save-log":
        row = data[sel[0]]
        log_interaction(row['quote_id'], status, date)
        return False, False
    return is_open, dash.no_update

# 6. HISTORY ACTIONS (EDIT / PDF)
@app.callback(
    [Output("main-tabs", "active_tab"), Output("dd-cust", "value", allow_duplicate=True),
     Output("job-type", "value"), Output("est-name", "value"),
     Output("cart-store", "data", allow_duplicate=True), Output("edit-mode", "data"),
     Output("download-pdf", "data"), Output("btn-edit", "disabled"), Output("btn-pdf", "disabled")],
    [Input("btn-edit", "n_clicks"), Input("btn-pdf", "n_clicks"), Input("hist-table", "selected_rows")],
    [State("hist-table", "data")], prevent_initial_call=True
)
def hist_actions(b_edit, b_pdf, sel, data):
    trig = ctx.triggered_id
    if trig == "hist-table":
        # Enable buttons if row selected
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update,
                dash.no_update, dash.no_update, dash.no_update, not bool(sel), not bool(sel))
    
    if not sel: return [dash.no_update]*9
    row = data[sel[0]]
    
    if trig == "btn-edit":
        h, items, _ = get_quote_detail(row['quote_id'])
        cart = [{"name": r['item_name'], "type": r['item_type'], "cost": r['unit_cost'], "price": r['unit_price'], "qty": r['quantity']} for _, r in items.iterrows()]
        emode = {"mode": "edit", "qid": row['quote_id']}
        return "tab-2", h['customer_id'], h['job_type'], h['estimator'], cart, emode, dash.no_update, True, True
        
    if trig == "btn-pdf":
        h, items, cname = get_quote_detail(row['quote_id'])
        cart = [{"name": r['item_name'], "price": r['unit_price'], "qty": r['quantity']} for _, r in items.iterrows()]
        f = generate_pdf(row['quote_id'], cname, cart, h['total_price'])
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dcc.send_file(f), False, False
        
    return [dash.no_update]*9

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)