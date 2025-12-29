import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, date
import pandas as pd
import psycopg2 
from psycopg2.extras import RealDictCursor
import json
import uuid
import random
import os
from flask import Flask
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================================
#  1. CONFIGURATION & DATABASE CONNECTION
# =========================================================
# In production, these are set in Render's dashboard
DATABASE_URL = os.environ.get("DATABASE_URL") 
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

server = Flask(__name__)
server.secret_key = SECRET_KEY

# --- Database Helper (PostgreSQL) ---
def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def execute_query(query, args=(), fetch=False):
    """
    Robust query executor that handles commits and closing connections automatically.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        if fetch:
            res = cur.fetchall()
            conn.close()
            return res
        conn.commit()
        conn.close()
    except Exception as e:
        conn.close()
        raise e

def get_df(query, args=()):
    """
    Returns a Pandas DataFrame from a SQL query.
    """
    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=args)
    conn.close()
    return df

# --- Auth Setup ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id, self.username, self.role = id, username, role

@login_manager.user_loader
def load_user(user_id):
    try:
        res = execute_query("SELECT id, username, role FROM users WHERE id = %s", (user_id,), fetch=True)
        return User(res[0]['id'], res[0]['username'], res[0]['role']) if res else None
    except:
        return None

# --- Initial Schema Setup ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tables designed for PostgreSQL
    c.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, type TEXT, notes TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT, items_json TEXT, subtotal REAL, tax REAL, discount REAL, fee REAL, total REAL, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, quote_id TEXT, customer_id TEXT, status TEXT, scheduled_date TEXT, tech TEXT, items_json TEXT, notes TEXT, total REAL)''')
    conn.commit()

    # Seed Admin if empty
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()['count'] == 0:
        print("--- SEEDING DATABASE ---")
        c.execute("INSERT INTO users VALUES (%s, %s, %s, %s)", ("U-1", "admin", generate_password_hash("admin123"), "Admin"))
        
        customers = [
            ("C-1", "Starbucks #402", "123 Latte Ln", "mgr@sbux.com", "555-0101", "Commercial", "Gate: 9999", datetime.now().isoformat()),
            ("C-2", "Hilton Hotel", "400 River St", "ap@hilton.com", "555-0102", "Commercial", "Check in at security", datetime.now().isoformat()),
        ]
        # Helper loop for seeding to avoid complex SQL string formatting differences
        for cust in customers:
            c.execute("INSERT INTO customers VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", cust)
        
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0),
        ]
        for cat in catalog:
            c.execute("INSERT INTO catalog VALUES (%s,%s,%s,%s,%s)", cat)
        conn.commit()
    
    conn.close()

# Only run init_db if we are actually running the server (prevents build errors)
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RENDER"): 
    try:
        init_db()
    except Exception as e:
        print(f"DB Init Skipped or Failed (Check connection string): {e}")

# =========================================================
#  2. STYLING & PDF ENGINE
# =========================================================
THEME = {"primary": "#0d6efd", "bg": "#f4f6f8", "sidebar": "#ffffff", "text": "#333"}
custom_css = f"""
    body {{ background-color: {THEME['bg']}; font-family: 'Inter', sans-serif; color: {THEME['text']}; }}
    .sidebar {{ position: fixed; top: 0; left: 0; bottom: 0; width: 250px; padding: 2rem 1rem; background: {THEME['sidebar']}; border-right: 1px solid #e0e0e0; z-index:10; }}
    .content {{ margin-left: 250px; padding: 2rem; }}
    @media (max-width: 768px) {{
        .sidebar {{ position: relative; width: 100%; height: auto; display: flex; overflow-x: auto; }}
        .content {{ margin-left: 0; }}
    }}
    .saas-card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); padding: 1.5rem; border: 1px solid #eaeaea; margin-bottom: 1.5rem; }}
    .nav-link {{ color: #555; font-weight: 500; margin-bottom: 0.5rem; border-radius: 6px; }}
    .nav-link.active {{ background-color: #e7f1ff; color: {THEME['primary']}; font-weight: 600; }}
    .status-pill {{ padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: bold; }}
    .status-Draft {{ background: #e2e3e5; color: #383d41; }}
    .status-Sent {{ background: #cff4fc; color: #055160; }}
    .status-Approved {{ background: #d1e7dd; color: #0f5132; }}
    .status-Scheduled {{ background: #cfe2ff; color: #084298; }}
"""

app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
app.index_string = '''<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>''' + custom_css + '''</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>'''

def create_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(13, 110, 253) 
    pdf.cell(0, 10, "TradeOps Inc.", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(0,0,0)
    pdf.cell(0, 10, f"Quote #: {data['id']} | Date: {date.today()}", ln=True)
    pdf.ln(10)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(120, 10, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Total", 1, 1, 'R', 1)
    pdf.set_font("Arial", "", 10)
    for item in data['items']:
        pdf.cell(120, 10, item['name'], 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(40, 10, f"${item['price']*item['qty']:.2f}", 1, 1, 'R')
    pdf.ln(5)
    pdf.cell(150, 10, "Total:", 0, 0, 'R')
    pdf.cell(40, 10, f"${data['total']:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#  3. VIEWS & COMPONENT LAYOUTS
# =========================================================
def LoginView():
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.H3("TradeOps Login", className="text-center fw-bold mb-4", style={"color": THEME['primary']}),
                dbc.Input(id="login-user", placeholder="Username", className="mb-3"),
                dbc.Input(id="login-pass", placeholder="Password", type="password", className="mb-3"),
                dbc.Button("Login", id="btn-login", color="primary", className="w-100"),
                html.Div(id="login-msg", className="text-danger text-center mt-3")
            ])
        ], style={"width": "350px", "padding": "20px"}, className="shadow border-0")
    ], style={"height": "100vh", "display": "flex", "alignItems": "center", "justifyContent": "center", "background": "#eef2f6"})

def Sidebar():
    return html.Div([
        html.H4([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": THEME['primary']}),
        dbc.Nav([
            dbc.NavLink("Dashboard", href="/", active="exact", className="mb-1"),
            dbc.NavLink("Dispatch Board", href="/dispatch", active="exact", className="mb-1"),
            dbc.NavLink("Quotes", href="/quotes", active="exact", className="mb-1"),
            dbc.NavLink("My Jobs", href="/jobs", active="exact", className="mb-1"),
            dbc.NavLink("Logout", href="/logout", className="text-danger mt-5"),
        ], vertical=True, pills=True)
    ], className="sidebar")

def DashboardView():
    df_q = get_df("SELECT * FROM quotes")
    df_j = get_df("SELECT * FROM jobs")
    rev = df_q['total'].sum() if not df_q.empty else 0
    return html.Div([
        html.H2("Dashboard", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue"), html.H3(f"${rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Open Quotes"), html.H3(str(len(df_q)), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Jobs"), html.H3(str(len(df_j)), className="fw-bold")], className="saas-card"), md=3),
        ])
    ])

def QuotesListView():
    df = get_df("SELECT q.id, c.name, q.status, q.total, q.created_at FROM quotes q JOIN customers c ON q.customer_id = c.id ORDER BY q.created_at DESC")
    return html.Div([
        dbc.Row([dbc.Col(html.H2("Quotes"), width=10), dbc.Col(dbc.Button("+ New", href="/builder/Q-NEW", color="primary"), width=2)]),
        dash_table.DataTable(id='quotes-table', data=df.to_dict('records'), columns=[{"name": i, "id": i} for i in ["id", "name", "status", "total"]], style_as_list_view=True, row_selectable='single', style_cell={'padding': '12px'})
    ], className="saas-card")

def QuoteBuilderView(qid):
    state = {"id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], "total": 0}
    if qid != "Q-NEW":
        rows = execute_query("SELECT * FROM quotes WHERE id=%s", (qid,), fetch=True)
        if rows:
            r = rows[0]
            state = {"id": r['id'], "status": r['status'], "customer_id": r['customer_id'], "items": json.loads(r['items_json']), "total": r['total']}
    
    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")
    return html.Div([
        dcc.Store(id="quote-state", data=state), dcc.Download(id="dl-pdf"),
        dbc.Button("← Back", href="/quotes", color="link"),
        dbc.Row([
            dbc.Col([html.H5("Client"), dcc.Dropdown(id="c-sel", options=[{'label':c['name'], 'value':c['id']} for _,c in customers.iterrows()], value=state['customer_id']), html.Div(id="q-acts", className="mt-3"), html.Div(id="q-toast")], md=4, className="saas-card"),
            dbc.Col([html.H5("Items"), dbc.Row([dbc.Col(dcc.Dropdown(id="cat-sel", options=[{'label':f"{x['name']} (${x['price']})", 'value':x['id']} for _,x in catalog.iterrows()]), width=8), dbc.Col(dbc.Button("Add", id="btn-add"), width=4)]), html.Div(id="cart"), html.H3(id="tot", className="text-end mt-3")], md=8, className="saas-card")
        ])
    ])

def DispatchBoardView():
    unassigned = get_df("SELECT j.id, c.name, j.total FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status = 'Unscheduled'")
    scheduled = get_df("SELECT j.*, c.name FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status IN ('Scheduled', 'Completed')")
    
    chart = html.Div("No schedule")
    if not scheduled.empty:
        chart = dcc.Graph(id="gantt", figure=px.timeline(scheduled, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="status", text="name").update_layout(height=400, template="plotly_white"))

    return html.Div([
        html.H2("Dispatch"),
        dbc.Row([
            dbc.Col([html.H5("Unassigned"), dash_table.DataTable(id='u-table', data=unassigned.to_dict('records'), columns=[{"name":"Job","id":"id"},{"name":"Client","id":"name"}], row_selectable='single', style_as_list_view=True)], md=3, className="saas-card"),
            dbc.Col([html.H5("Schedule"), chart], md=9, className="saas-card")
        ]),
        dbc.Modal([dbc.ModalHeader("Assign"), dbc.ModalBody([dcc.Input(id="d-jid", type="hidden"), dbc.Select(id="d-tech", options=[{"label":t,"value":t} for t in ["Mike","Sarah"]]), dcc.DatePickerSingle(id="d-date", date=date.today(), display_format="YYYY-MM-DD")]), dbc.ModalFooter(dbc.Button("Confirm", id="btn-d-ok", color="primary"))], id="d-modal", is_open=False)
    ])

def JobView(jid):
    res = execute_query("SELECT j.*, c.name, c.address FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.id = %s", (jid,), fetch=True)
    if not res: return html.Div("Job not found")
    job = res[0]
    items = json.loads(job['items_json'])
    return html.Div([
        dcc.Store(id="j-state", data={"id":jid, "items":items}),
        dbc.Button("← Dispatch", href="/dispatch", color="link"),
        html.H2(f"Job: {jid}"),
        dbc.Row([
            dbc.Col([html.P(f"Client: {job['name']}"), html.P(f"Addr: {job['address']}"), dbc.Button("Complete", id="btn-j-comp", color="success")], md=4, className="saas-card"),
            dbc.Col([html.Div(id="j-cart"), dbc.Input(id="j-add-n", placeholder="Part Name"), dbc.Button("Add Part", id="btn-j-add", className="mt-2")], md=8, className="saas-card")
        ])
    ])

# =========================================================
#  4. APP ROUTING & CALLBACKS
# =========================================================
app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def router(path):
    if path == "/login": return LoginView()
    if path == "/logout": logout_user(); return LoginView()
    if not current_user.is_authenticated: return LoginView()
    if path == "/" or path == "/dashboard": return DashboardView()
    if path == "/quotes": return QuotesListView()
    if path == "/dispatch": return DispatchBoardView()
    if path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    if path.startswith("/job/"): return JobView(path.split("/")[-1])
    return DashboardView()

@app.callback([Output("url", "pathname"), Output("login-msg", "children")], Input("btn-login", "n_clicks"), [State("login-user", "value"), State("login-pass", "value")], prevent_initial_call=True)
def login_act(n, u, p):
    res = execute_query("SELECT id, password_hash, role FROM users WHERE username=%s", (u,), fetch=True)
    if res and check_password_hash(res[0]['password_hash'], p):
        login_user(User(res[0]['id'], u, res[0]['role']))
        return "/", ""
    return dash.no_update, "Invalid"

@app.callback([Output("quote-state", "data"), Output("cart", "children"), Output("tot", "children"), Output("q-acts", "children"), Output("dl-pdf", "data"), Output("q-toast", "children")], [Input("btn-add", "n_clicks"), Input({"type":"a-btn", "index":ALL}, "n_clicks")], [State("cat-sel", "value"), State("quote-state", "data"), State("c-sel", "value")])
def quote_logic(n_add, n_act, cat_id, state, cust_id):
    ctx_id = ctx.triggered_id
    pdf, toast = dash.no_update, None
    state['customer_id'] = cust_id
    if ctx_id == "btn-add" and cat_id:
        item = execute_query("SELECT * FROM catalog WHERE id=%s", (cat_id,), fetch=True)[0]
        state['items'].append({"name":item['name'], "qty":1, "price":item['price']})
    state['total'] = sum(i['qty']*i['price'] for i in state['items'])
    
    if isinstance(ctx_id, dict) and ctx_id['type'] == "a-btn":
        act = ctx_id['index']
        vals = (state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), json.dumps(state['items']), 0,0,0,0, state['total'], "")
        if act == "save":
            if state['id'] == "Q-NEW":
                state['id'] = f"Q-{random.randint(10000,99999)}"
                execute_query("INSERT INTO quotes VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (state['id'],)+vals)
            else:
                execute_query("UPDATE quotes SET customer_id=%s, status=%s, created_at=%s, items_json=%s, subtotal=%s, tax=%s, discount=%s, fee=%s, total=%s, notes=%s WHERE id=%s", vals+(state['id'],))
            toast = dbc.Toast("Saved", header="Success", icon="success", duration=2000, style={"position":"fixed", "top":10, "right":10})
        elif act == "approve":
            execute_query("UPDATE quotes SET status='Approved' WHERE id=%s", (state['id'],))
            execute_query("INSERT INTO jobs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (f"J-{random.randint(1000,9999)}", state['id'], state['customer_id'], "Unscheduled", None, None, json.dumps(state['items']), "", state['total']))
            state['status'] = "Approved"
        elif act == "pdf":
            pdf = dcc.send_bytes(create_pdf(state), "quote.pdf")

    cart = [dbc.Row([dbc.Col(i['name']), dbc.Col(f"${i['price']}")]) for i in state['items']]
    btns = [dbc.Button("Save", id={"type":"a-btn", "index":"save"}, className="me-2"), dbc.Button("PDF", id={"type":"a-btn", "index":"pdf"}, color="info")]
    if state['status'] == "Draft": btns.append(dbc.Button("Approve", id={"type":"a-btn", "index":"approve"}, color="success", className="ms-2"))
    return state, cart, f"${state['total']:,.2f}", btns, pdf, toast

@app.callback([Output("d-modal", "is_open"), Output("d-jid", "value"), Output("url", "pathname", allow_duplicate=True)], [Input("u-table", "selected_rows"), Input("gantt", "clickData"), Input("btn-d-ok", "n_clicks")], [State("u-table", "data"), State("d-jid", "value"), State("d-tech", "value"), State("d-date", "date")], prevent_initial_call=True)
def dispatch_logic(sel, click, ok, data, jid, tech, dt):
    if ctx.triggered_id == "u-table" and sel: return True, data[sel[0]]['id'], dash.no_update
    if ctx.triggered_id == "gantt" and click: return False, "", f"/job/{click['points'][0]['customdata'][0]}" 
    if ctx.triggered_id == "btn-d-ok":
        execute_query("UPDATE jobs SET status='Scheduled', tech=%s, scheduled_date=%s WHERE id=%s", (tech, dt, jid))
        return False, "", "/dispatch"
    return False, "", dash.no_update

@app.callback(Output("url", "pathname", allow_duplicate=True), Input("quotes-table", "selected_rows"), State("quotes-table", "data"), prevent_initial_call=True)
def nav_q(sel, data): return f"/builder/{data[sel[0]]['id']}"

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
