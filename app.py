import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, date
import pandas as pd
import sqlite3
import json
import uuid
import random
from flask import Flask
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# =========================================================
#  1. SETUP: FLASK, SECURITY & DATABASE
# =========================================================
DB_FILE = "tradeops_enterprise.db"
server = Flask(__name__)
server.secret_key = "SuperSecretKey123" # Change this for production

# --- Auth Setup ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id, self.username, self.role = id, username, role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return User(res[0], res[1], res[2]) if res else None

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Auth
    c.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT)''')
    
    # ERP Data
    c.execute('''CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, type TEXT, notes TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT, items_json TEXT, subtotal REAL, tax REAL, discount REAL, fee REAL, total REAL, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, quote_id TEXT, customer_id TEXT, status TEXT, scheduled_date TEXT, tech TEXT, items_json TEXT, notes TEXT, total REAL)''')

    # Seed Admin User
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        print("--- SEEDING DATA ---")
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("U-1", "admin", generate_password_hash("admin123"), "Admin"))
        
        # Seed Customers
        customers = [
            ("C-1", "Starbucks #402", "123 Latte Ln", "mgr@sbux.com", "555-0101", "Commercial", "Gate: 9999", datetime.now().isoformat()),
            ("C-2", "Hilton Hotel", "400 River St", "ap@hilton.com", "555-0102", "Commercial", "Check in at security", datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
        
        # Seed Catalog
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0),
        ]
        c.executemany("INSERT INTO catalog VALUES (?,?,?,?,?)", catalog)

    conn.commit()
    conn.close()

init_db()

# --- DB Helpers ---
def get_df(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(query, conn, params=args)
    conn.close()
    return df

def execute_query(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, args)
    conn.commit()
    conn.close()

# =========================================================
#  2. STYLING & PDF ENGINE
# =========================================================
THEME = {"primary": "#0d6efd", "bg": "#f4f6f8", "sidebar": "#ffffff", "text": "#333"}

custom_css = f"""
    body {{ background-color: {THEME['bg']}; font-family: 'Inter', sans-serif; color: {THEME['text']}; }}
    .sidebar {{ position: fixed; top: 0; left: 0; bottom: 0; width: 250px; padding: 2rem 1rem; background: {THEME['sidebar']}; border-right: 1px solid #e0e0e0; }}
    .content {{ margin-left: 250px; padding: 2rem; }}
    .login-container {{ height: 100vh; display: flex; align-items: center; justify-content: center; background: #eef2f6; }}
    .saas-card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); padding: 1.5rem; border: 1px solid #eaeaea; margin-bottom: 1.5rem; }}
    .nav-link {{ color: #555; font-weight: 500; margin-bottom: 0.5rem; border-radius: 6px; }}
    .nav-link.active {{ background-color: #e7f1ff; color: {THEME['primary']}; font-weight: 600; }}
    .status-pill {{ padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: bold; }}
    .status-Draft {{ background: #e2e3e5; color: #383d41; }}
    .status-Sent {{ background: #cff4fc; color: #055160; }}
    .status-Approved {{ background: #d1e7dd; color: #0f5132; }}
    .status-Unscheduled {{ background: #fff3cd; color: #856404; }}
    .status-Scheduled {{ background: #cfe2ff; color: #084298; }}
"""

app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field Service"
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
    pdf.set_font("Arial", "B", 12)
    pdf.cell(150, 10, "Total:", 0, 0, 'R')
    pdf.cell(40, 10, f"${data['total']:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#  3. COMPONENT VIEWS
# =========================================================

def LoginView():
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.H3("TradeOps Login", className="text-center fw-bold mb-4", style={"color": THEME['primary']}),
                dbc.Input(id="login-user", placeholder="Username (admin)", className="mb-3"),
                dbc.Input(id="login-pass", placeholder="Password (admin123)", type="password", className="mb-3"),
                dbc.Button("Login", id="btn-login", color="primary", className="w-100"),
                html.Div(id="login-msg", className="text-danger text-center mt-3")
            ])
        ], style={"width": "350px", "padding": "20px"}, className="shadow border-0")
    ], className="login-container")

def Sidebar():
    return html.Div([
        html.H4([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": THEME['primary']}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-range me-2"), "Dispatch Board"], href="/dispatch", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-text me-2"), "Quotes"], href="/quotes", active="exact"),
            dbc.NavLink([html.I(className="bi bi-tools me-2"), "My Jobs"], href="/jobs", active="exact"),
            dbc.NavLink([html.I(className="bi bi-people me-2"), "Accounts"], href="/accounts", active="exact"),
            dbc.NavLink([html.I(className="bi bi-box-arrow-right me-2"), "Logout"], href="/logout", className="text-danger mt-5"),
        ], vertical=True, pills=True)
    ], className="sidebar")

def DashboardView():
    df_q = get_df("SELECT * FROM quotes")
    df_j = get_df("SELECT * FROM jobs")
    return html.Div([
        html.H2("Dashboard", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue"), html.H3(f"${df_q['total'].sum():,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Open Quotes"), html.H3(len(df_q[df_q['status']!='Approved']), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Active Jobs"), html.H3(len(df_j[df_j['status']!='Completed']), className="fw-bold")], className="saas-card"), md=3),
        ])
    ])

def QuotesListView():
    df = get_df("SELECT q.id, c.name, q.status, q.total, q.created_at FROM quotes q JOIN customers c ON q.customer_id = c.id ORDER BY q.created_at DESC")
    return html.Div([
        dbc.Row([dbc.Col(html.H2("Quotes"), width=10), dbc.Col(dbc.Button("+ New Quote", href="/builder/Q-NEW", color="primary"), width=2)]),
        html.Div(dash_table.DataTable(
            id='quotes-table', data=df.to_dict('records'),
            columns=[{"name": i, "id": i} for i in ["id", "name", "status", "total", "created_at"]],
            style_as_list_view=True, row_selectable='single',
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '12px'}
        ), className="saas-card")
    ])

def QuoteBuilderView(qid):
    # Load State
    state = {"id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], "total": 0}
    if qid != "Q-NEW":
        row = get_df("SELECT * FROM quotes WHERE id=?", (qid,)).iloc[0]
        state = {"id": row['id'], "status": row['status'], "customer_id": row['customer_id'], "items": json.loads(row['items_json']), "total": row['total']}
    
    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")
    
    return html.Div([
        dcc.Store(id="quote-state", data=state),
        dcc.Download(id="download-pdf"),
        dbc.Button("← Back", href="/quotes", color="link", className="mb-2 ps-0"),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Customer Info", className="fw-bold"),
                    dcc.Dropdown(id="cust-select", options=[{'label':c['name'], 'value':c['id']} for _,c in customers.iterrows()], value=state['customer_id']),
                    html.Hr(),
                    html.Div(id="quote-actions"),
                    html.Div(id="toast-anchor")
                ], className="saas-card h-100")
            ], md=4),
            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="cat-select", options=[{'label':f"{r['name']} (${r['price']})", 'value':r['id']} for _,r in catalog.iterrows()], placeholder="Select Item..."), md=8),
                        dbc.Col(dbc.Button("Add", id="btn-add-item", color="dark", className="w-100"), md=4)
                    ], className="mb-3"),
                    html.Div(id="cart-container"),
                    html.H3(id="total-display", className="text-end fw-bold text-success mt-3")
                ], className="saas-card h-100")
            ], md=8)
        ])
    ])

def DispatchBoardView():
    unassigned = get_df("SELECT j.id, c.name, j.total FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status = 'Unscheduled'")
    scheduled = get_df("SELECT j.*, c.name FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status IN ('Scheduled', 'Completed')")
    
    gantt = html.Div("No scheduled jobs", className="p-5 text-center text-muted")
    if not scheduled.empty:
        gantt = dcc.Graph(id="gantt-chart", figure=px.timeline(scheduled, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="status", text="name").update_layout(template="plotly_white", height=400))

    return html.Div([
        html.H2("Dispatch Board", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([
                html.H5("Unassigned Bucket", className="fw-bold text-danger"),
                dash_table.DataTable(id='dispatch-table', data=unassigned.to_dict('records'), columns=[{"name": "Job", "id": "id"}, {"name": "Client", "id": "name"}], row_selectable='single', style_as_list_view=True)
            ], className="saas-card h-100"), md=3),
            dbc.Col(html.Div([html.H5("Schedule", className="fw-bold"), gantt], className="saas-card h-100"), md=9)
        ]),
        dbc.Modal([
            dbc.ModalHeader("Assign Technician"),
            dbc.ModalBody([
                dcc.Input(id="disp-jid", type="hidden"),
                dbc.Label("Technician"),
                dbc.Select(id="disp-tech", options=[{"label":t,"value":t} for t in ["Mike", "Sarah", "Elliott"]]),
                dbc.Label("Date", className="mt-2"),
                dcc.DatePickerSingle(id="disp-date", date=date.today(), display_format="YYYY-MM-DD", className="d-block")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm Assignment", id="btn-dispatch-confirm", color="primary"))
        ], id="dispatch-modal", is_open=False)
    ])

def JobView(jid):
    job = get_df("SELECT j.*, c.name, c.address FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.id = ?", (jid,)).iloc[0]
    items = json.loads(job['items_json'])
    return html.Div([
        dcc.Store(id="job-state", data={"id": jid, "items": items}),
        dbc.Button("← Back", href="/dispatch", color="link", className="mb-2 ps-0"),
        html.H2(f"Job: {jid}", className="fw-bold"),
        html.Span(job['status'], className=f"status-pill status-{job['status']} mb-4 d-inline-block"),
        dbc.Row([
            dbc.Col(html.Div([
                html.H5("Details"), html.P(f"Client: {job['name']}"), html.P(f"Address: {job['address']}"),
                dbc.Button("Complete Job", id="btn-complete", color="success", className="w-100 mt-3")
            ], className="saas-card"), md=4),
            dbc.Col(html.Div([
                html.H5("Work Order"),
                html.Div(id="job-cart"),
                dbc.Input(id="tech-add-name", placeholder="Add Part...", className="mt-3"),
                dbc.Button("Add", id="btn-tech-add", color="secondary", className="mt-2")
            ], className="saas-card"), md=8)
        ])
    ])

# =========================================================
#  4. APP ROUTING & LOGIC
# =========================================================
app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(path):
    if path == "/login": return LoginView()
    if path == "/logout": 
        logout_user()
        return LoginView()
    
    if not current_user.is_authenticated:
        return LoginView()

    content = html.Div("404 Not Found")
    if path == "/" or path == "/dashboard": content = DashboardView()
    elif path == "/quotes": content = QuotesListView()
    elif path == "/dispatch": content = DispatchBoardView()
    elif path == "/jobs": content = QuotesListView() # Placeholder
    elif path.startswith("/builder/"): content = QuoteBuilderView(path.split("/")[-1])
    elif path.startswith("/job/"): content = JobView(path.split("/")[-1])
    
    return html.Div([Sidebar(), html.Div(content, className="content")])

# --- Login Logic ---
@app.callback(
    [Output("url", "pathname"), Output("login-msg", "children")],
    Input("btn-login", "n_clicks"), [State("login-user", "value"), State("login-pass", "value")],
    prevent_initial_call=True
)
def login(n, user, pwd):
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute("SELECT id, password_hash, role FROM users WHERE username=?", (user,)).fetchone()
    conn.close()
    if res and check_password_hash(res[1], pwd):
        login_user(User(res[0], user, res[2]))
        return "/", ""
    return dash.no_update, "Invalid Credentials"

# --- Quote Logic ---
@app.callback(
    [Output("quote-state", "data"), Output("cart-container", "children"), Output("total-display", "children"), Output("quote-actions", "children"), Output("download-pdf", "data"), Output("toast-anchor", "children")],
    [Input("btn-add-item", "n_clicks"), Input({"type":"act-btn", "index":ALL}, "n_clicks")],
    [State("cat-select", "value"), State("quote-state", "data"), State("cust-select", "value")]
)
def quote_logic(n_add, n_act, cat_id, state, cust_id):
    ctx_id = ctx.triggered_id
    pdf, toast = dash.no_update, None
    state['customer_id'] = cust_id
    
    if ctx_id == "btn-add-item" and cat_id:
        item = get_df("SELECT * FROM catalog WHERE id=?", (cat_id,)).iloc[0]
        state['items'].append({"name":item['name'], "qty":1, "price":item['price']})
    
    state['total'] = sum(i['qty']*i['price'] for i in state['items'])
    
    if isinstance(ctx_id, dict) and ctx_id['type'] == "act-btn":
        act = ctx_id['index']
        if act == "save":
            vals = (state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), json.dumps(state['items']), 0,0,0,0, state['total'], "")
            if state['id'] == "Q-NEW":
                state['id'] = f"Q-{random.randint(10000,99999)}"
                execute_query("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?)", (state['id'],)+vals)
            else:
                execute_query("UPDATE quotes SET customer_id=?, status=?, created_at=?, items_json=?, subtotal=?, tax=?, discount=?, fee=?, total=?, notes=? WHERE id=?", vals+(state['id'],))
            toast = dbc.Toast("Saved Successfully", header="Success", icon="success", duration=2000, style={"position":"fixed", "top":10, "right":10})
        elif act == "approve":
             execute_query("UPDATE quotes SET status='Approved' WHERE id=?", (state['id'],))
             execute_query("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)", (f"J-{random.randint(1000,9999)}", state['id'], state['customer_id'], "Unscheduled", None, None, json.dumps(state['items']), "", state['total']))
             state['status'] = "Approved"
        elif act == "pdf":
            pdf = dcc.send_bytes(create_pdf(state), "quote.pdf")

    cart = [dbc.Row([dbc.Col(i['name']), dbc.Col(f"${i['price']}")] ) for i in state['items']]
    btns = [dbc.Button("Save", id={"type":"act-btn", "index":"save"}, color="secondary", className="me-2"), dbc.Button("PDF", id={"type":"act-btn", "index":"pdf"}, color="info", className="me-2")]
    if state['status'] == "Draft": btns.append(dbc.Button("Approve & Create Job", id={"type":"act-btn", "index":"approve"}, color="success"))
    
    return state, cart, f"${state['total']:,.2f}", btns, pdf, toast

# --- Dispatch Logic ---
@app.callback(
    [Output("dispatch-modal", "is_open"), Output("disp-jid", "value"), Output("url", "pathname", allow_duplicate=True)],
    [Input("dispatch-table", "selected_rows"), Input("gantt-chart", "clickData"), Input("btn-dispatch-confirm", "n_clicks")],
    [State("dispatch-table", "data"), State("disp-jid", "value"), State("disp-tech", "value"), State("disp-date", "date")],
    prevent_initial_call=True
)
def dispatch(rows, click, confirm, data, jid, tech, dt):
    if ctx.triggered_id == "dispatch-table" and rows: return True, data[rows[0]]['id'], dash.no_update
    if ctx.triggered_id == "gantt-chart" and click: return False, "", f"/job/{click['points'][0]['customdata'][0]}" # Requires customdata, simplified here to look good
    if ctx.triggered_id == "btn-dispatch-confirm":
        execute_query("UPDATE jobs SET status='Scheduled', tech=?, scheduled_date=? WHERE id=?", (tech, dt, jid))
        return False, "", "/dispatch"
    return False, "", dash.no_update

# --- Job Logic ---
@app.callback([Output("job-cart", "children"), Output("job-state", "data")], [Input("btn-tech-add", "n_clicks"), Input("btn-complete", "n_clicks")], [State("tech-add-name", "value"), State("job-state", "data")])
def job_update(n_add, n_comp, name, state):
    if ctx.triggered_id == "btn-tech-add" and name:
        state['items'].append({"name": name, "qty": 1, "price": 0})
    if ctx.triggered_id == "btn-complete":
        execute_query("UPDATE jobs SET status='Completed', items_json=? WHERE id=?", (json.dumps(state['items']), state['id']))
    
    cart = [dbc.Row([dbc.Col(i['name']), dbc.Col(f"${i['price']}")] ) for i in state['items']]
    return cart, state

# --- Navigation ---
@app.callback(Output("url", "pathname", allow_duplicate=True), Input("quotes-table", "selected_rows"), State("quotes-table", "data"), prevent_initial_call=True)
def nav_quote(rows, data):
    if rows: return f"/builder/{data[rows[0]]['id']}"
    return dash.no_update

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
