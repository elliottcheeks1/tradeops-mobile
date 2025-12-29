import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
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
#  1. CONFIGURATION & DATABASE
# =========================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

server = Flask(__name__)
server.secret_key = SECRET_KEY

def get_db_connection():
    if not DATABASE_URL: raise ValueError("DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def execute_query(query, args=(), fetch=False):
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
    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=args)
    conn.close()
    return df

# --- Auth ---
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
    except: return None

# --- Init DB ---
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RENDER"):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, type TEXT, notes TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, created_at TEXT, items_json TEXT, subtotal REAL, tax REAL, discount REAL, fee REAL, total REAL, notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, quote_id TEXT, customer_id TEXT, status TEXT, scheduled_date TEXT, tech TEXT, items_json TEXT, notes TEXT, total REAL)''')
        conn.commit()
        
        # Seeding
        c.execute("SELECT count(*) as cnt FROM users")
        if c.fetchone()['cnt'] == 0:
            print("--- SEEDING DATA ---")
            c.execute("INSERT INTO users VALUES (%s, %s, %s, %s)", ("U-1", "admin", generate_password_hash("admin123"), "Admin"))
            c.execute("INSERT INTO customers VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", ("C-1", "Starbucks #402", "1912 Pike Place, Seattle, WA", "mgr@sbux.com", "206-555-0101", "Commercial", "Check in at back gate", datetime.now().isoformat()))
            c.execute("INSERT INTO customers VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", ("C-2", "Hilton Union Square", "333 O'Farrell St, San Francisco, CA", "ap@hilton.com", "415-555-0199", "Commercial", "Front desk", datetime.now().isoformat()))
            c.execute("INSERT INTO catalog VALUES (%s,%s,%s,%s,%s)", ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0))
            c.execute("INSERT INTO catalog VALUES (%s,%s,%s,%s,%s)", ("L-1", "Master Labor", "Labor", 60.0, 185.0))
            conn.commit()
        conn.close()
    except Exception as e: print(f"DB Init Warning: {e}")

# =========================================================
#  2. DESIGN SYSTEM (CSS)
# =========================================================
# This CSS transforms Bootstrap into the "TradeOps" SaaS look
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --primary: #2563EB; /* Royal Blue */
    --primary-light: #EFF6FF;
    --text-dark: #1F2937;
    --text-light: #6B7280;
    --bg-main: #F9FAFB;
    --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
}

body { background-color: var(--bg-main); font-family: 'Inter', sans-serif; color: var(--text-dark); -webkit-font-smoothing: antialiased; }

/* Sidebar */
.sidebar { 
    position: fixed; top: 0; left: 0; bottom: 0; width: 260px; 
    background: #FFFFFF; border-right: 1px solid #E5E7EB; 
    padding: 2rem 1.5rem; z-index: 50;
}
.content { margin-left: 260px; padding: 2.5rem; }

/* Navigation Links */
.nav-link { 
    color: var(--text-light); font-weight: 500; padding: 0.75rem 1rem; 
    border-radius: 8px; transition: all 0.2s; margin-bottom: 4px; display: flex; align-items: center;
}
.nav-link:hover { background-color: #F3F4F6; color: var(--text-dark); }
.nav-link.active { background-color: var(--primary-light); color: var(--primary); font-weight: 600; }
.nav-link i { margin-right: 12px; font-size: 1.1rem; }

/* Cards */
.saas-card { 
    background: #FFFFFF; border-radius: 12px; border: 1px solid #E5E7EB;
    box-shadow: var(--card-shadow); padding: 1.5rem; margin-bottom: 1.5rem;
    transition: transform 0.2s;
}

/* Typography */
h2, h3, h4, h5 { font-weight: 700; color: #111827; letter-spacing: -0.025em; }
.text-label { color: var(--text-light); font-size: 0.875rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }

/* Buttons */
.btn-primary { 
    background-color: var(--primary); border: none; padding: 0.6rem 1.2rem; 
    font-weight: 500; border-radius: 8px; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); 
}
.btn-primary:hover { background-color: #1D4ED8; }
.btn-link { text-decoration: none; color: var(--text-light); }
.btn-link:hover { color: var(--primary); }

/* Status Pills */
.badge-pill { padding: 4px 12px; border-radius: 99px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.status-Approved, .status-Completed { background-color: #D1FAE5; color: #065F46; } /* Green */
.status-Draft, .status-Unscheduled { background-color: #FEF3C7; color: #92400E; } /* Yellow */
.status-Sent, .status-Scheduled { background-color: #DBEAFE; color: #1E40AF; } /* Blue */

/* Tables */
.dash-spreadsheet-container .dash-spreadsheet-inner th { 
    background-color: #F9FAFB !important; color: var(--text-light) !important; 
    font-weight: 600 !important; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; border-bottom: 1px solid #E5E7EB !important; 
}
.dash-spreadsheet-container .dash-spreadsheet-inner td { 
    border-bottom: 1px solid #F3F4F6 !important; padding: 16px !important; color: var(--text-dark); font-size: 0.95rem;
}
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover td { background-color: #F9FAFB !important; }

/* Mobile */
@media (max-width: 768px) {
    .sidebar { width: 100%; height: auto; position: relative; display: flex; overflow-x: auto; padding: 1rem; border-bottom: 1px solid #E5E7EB; border-right: none; white-space: nowrap; }
    .content { margin-left: 0; padding: 1rem; }
}
"""

app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps"
app.index_string = f'''<!DOCTYPE html><html><head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}<style>{custom_css}</style></head><body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body></html>'''

# =========================================================
#  3. HELPER FUNCTIONS (PDF & MAP)
# =========================================================
def create_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(37, 99, 235) 
    pdf.cell(0, 10, "TradeOps", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Quote #: {data['id']} | Date: {date.today()}", ln=True)
    pdf.ln(10)
    pdf.set_fill_color(249, 250, 251)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(0,0,0)
    pdf.cell(110, 10, "DESCRIPTION", 0, 0, 'L', 1)
    pdf.cell(30, 10, "QTY", 0, 0, 'C', 1)
    pdf.cell(50, 10, "TOTAL", 0, 1, 'R', 1)
    pdf.set_font("Arial", "", 10)
    for item in data['items']:
        pdf.cell(110, 12, item['name'], 0, 0, 'L')
        pdf.cell(30, 12, str(item['qty']), 0, 0, 'C')
        pdf.cell(50, 12, f"${item['price']*item['qty']:.2f}", 0, 1, 'R')
        pdf.ln(0)
        pdf.cell(0,0, "", "B") # underline
        pdf.ln(12)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(140, 10, "Total Due:", 0, 0, 'R')
    pdf.cell(50, 10, f"${data['total']:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def generate_map(lat=47.6062, lon=-122.3321):
    fig = go.Figure(go.Scattermapbox(lat=[lat], lon=[lon], mode='markers', marker=go.scattermapbox.Marker(size=14, color='#2563EB'), text=["Job Site"]))
    fig.update_layout(mapbox_style="open-street-map", mapbox_center_lat=lat, mapbox_center_lon=lon, mapbox_zoom=13, margin={"r":0,"t":0,"l":0,"b":0}, height=300)
    return fig

# =========================================================
#  4. UI COMPONENTS (SIDEBAR & VIEWS)
# =========================================================

def LoginView():
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.H3([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="text-center fw-bold mb-4", style={"color": "#2563EB"}),
                html.P("Sign in to your account", className="text-center text-muted mb-4"),
                dbc.Input(id="login-user", placeholder="Username", className="mb-3 p-3"),
                dbc.Input(id="login-pass", placeholder="Password", type="password", className="mb-4 p-3"),
                dbc.Button("Sign In", id="btn-login", color="primary", className="w-100 p-2"),
                html.Div(id="login-msg", className="text-danger text-center mt-3 small")
            ])
        ], style={"width": "400px"}, className="border-0 shadow-lg")
    ], style={"height": "100vh", "display": "flex", "alignItems": "center", "justifyContent": "center", "background": "#F3F4F6"})

def Sidebar():
    return html.Div([
        html.H4([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": "#2563EB", "paddingLeft":"10px"}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-grid-fill"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-range-fill"), "Dispatch Board"], href="/dispatch", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text-fill"), "Quotes"], href="/quotes", active="exact"),
            dbc.NavLink([html.I(className="bi bi-tools"), "Jobs List"], href="/jobs", active="exact"),
            dbc.NavLink([html.I(className="bi bi-people-fill"), "Accounts"], href="/accounts", active="exact"),
        ], vertical=True, pills=True),
        html.Div([
            html.Hr(),
            html.Div([
                html.Div([html.H6(current_user.username.title(), className="mb-0"), html.Small(current_user.role, className="text-muted")], className="ms-2")
            ], className="d-flex align-items-center mb-3"),
            dbc.NavLink([html.I(className="bi bi-box-arrow-right"), "Logout"], href="/logout", className="text-danger ps-2")
        ], style={"position": "absolute", "bottom": "20px", "width": "85%"})
    ], className="sidebar")

def MetricCard(title, value, subtext, icon, color="primary"):
    return dbc.Col(html.Div([
        html.Div([html.H6(title, className="text-label mb-2"), html.I(className=f"bi {icon} fs-4 text-{color}")] , className="d-flex justify-content-between"),
        html.H3(value, className="fw-bold mb-1"),
        html.Small(subtext, className=f"text-{color}")
    ], className="saas-card h-100"), md=3)

def DashboardView():
    df_q = get_df("SELECT * FROM quotes")
    df_j = get_df("SELECT * FROM jobs")
    rev = df_q[df_q['status']=='Approved']['total'].sum()
    open_q = len(df_q[df_q['status']=='Draft'])
    
    return html.Div([
        html.H2("Executive Dashboard", className="fw-bold mb-4"),
        dbc.Row([
            MetricCard("Total Revenue", f"${rev:,.0f}", "+12% vs last month", "bi-currency-dollar", "success"),
            MetricCard("Open Quotes", str(open_q), "Requires attention", "bi-file-earmark-text", "warning"),
            MetricCard("Active Jobs", str(len(df_j[df_j['status']!='Completed'])), "In progress", "bi-tools", "primary"),
            MetricCard("Tech Utilization", "85%", "High demand", "bi-lightning", "info"),
        ]),
        dbc.Row([
            dbc.Col(html.Div([
                html.H5("Recent Activity", className="fw-bold mb-4"),
                html.Div("No recent activity.", className="text-muted fst-italic")
            ], className="saas-card h-100"), md=8),
            dbc.Col(html.Div([
                html.H5("Quick Actions", className="fw-bold mb-3"),
                dbc.Button([html.I(className="bi bi-plus-lg me-2"), "New Quote"], href="/builder/Q-NEW", color="primary", className="w-100 mb-3 py-2"),
                dbc.Button([html.I(className="bi bi-calendar-event me-2"), "Dispatch Board"], href="/dispatch", color="light", className="w-100 py-2 text-dark border")
            ], className="saas-card h-100"), md=4)
        ], className="mt-3")
    ])

def QuotesListView():
    df = get_df("SELECT q.id, c.name, q.status, q.total, q.created_at FROM quotes q JOIN customers c ON q.customer_id = c.id ORDER BY q.created_at DESC")
    # Apply custom pill styling to status
    data = df.to_dict('records')
    
    return html.Div([
        dbc.Row([dbc.Col(html.H2("Quotes", className="fw-bold"), width=9), dbc.Col(dbc.Button("+ Create Quote", href="/builder/Q-NEW", color="primary", className="float-end"), width=3)]),
        html.Div(dash_table.DataTable(
            id='quotes-table', data=data,
            columns=[
                {"name": "QUOTE ID", "id": "id"}, 
                {"name": "CUSTOMER", "id": "name"}, 
                {"name": "DATE", "id": "created_at"}, 
                {"name": "TOTAL", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}},
                {"name": "STATUS", "id": "status"}
            ],
            style_as_list_view=True, row_selectable='single',
            style_cell={'fontFamily': 'Inter', 'textAlign': 'left'},
            style_header={'backgroundColor': 'white', 'borderBottom': '2px solid #eee', 'padding': '12px'},
            style_data={'borderBottom': '1px solid #eee'},
            style_data_conditional=[
                {'if': {'filter_query': '{status} = "Approved"', 'column_id': 'status'}, 'color': '#065F46', 'backgroundColor': '#D1FAE5', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{status} = "Draft"', 'column_id': 'status'}, 'color': '#92400E', 'backgroundColor': '#FEF3C7', 'fontWeight': 'bold'},
            ]
        ), className="saas-card mt-3")
    ])

def QuoteBuilderView(qid):
    state = {"id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], "total": 0}
    if qid != "Q-NEW":
        rows = execute_query("SELECT * FROM quotes WHERE id=%s", (qid,), fetch=True)
        if rows:
            r = rows[0]
            state = {"id": r['id'], "status": r['status'], "customer_id": r['customer_id'], "items": json.loads(r['items_json']), "total": r['total']}
    
    customers = get_df("SELECT id, name, address, phone FROM customers")
    catalog = get_df("SELECT * FROM catalog")
    
    return html.Div([
        dcc.Store(id="quote-state", data=state), dcc.Download(id="dl-pdf"),
        dbc.Row([
            dbc.Col(html.A([html.I(className="bi bi-arrow-left me-2"), "Back to Quotes"], href="/quotes", className="text-decoration-none text-muted mb-3 d-block"), width=12)
        ]),
        html.Div([
            dbc.Row([
                dbc.Col(html.H3(f"Quote {state['id']}", className="fw-bold"), width=8),
                dbc.Col(html.Span(state['status'], className=f"badge-pill status-{state['status']} float-end"), width=4)
            ], className="mb-4 border-bottom pb-3"),
            
            dbc.Row([
                dbc.Col([
                    html.Label("CUSTOMER", className="text-label mb-2"),
                    dcc.Dropdown(id="c-sel", options=[{'label':c['name'], 'value':c['id']} for _,c in customers.iterrows()], value=state['customer_id'], placeholder="Select Customer...", className="mb-3"),
                    html.Div(id="cust-details-placeholder", className="text-muted small mb-3"),
                    html.Label("NOTES", className="text-label mb-2"),
                    dbc.Textarea(id="q-notes", placeholder="Internal notes...", style={"height": "100px", "background": "#F9FAFB"})
                ], md=4, className="pe-4 border-end"),
                
                dbc.Col([
                    html.Label("LINE ITEMS", className="text-label mb-2"),
                    dbc.InputGroup([
                        dbc.Select(id="cat-sel", options=[{'label':f"{x['name']} (${x['price']})", 'value':x['id']} for _,x in catalog.iterrows()], placeholder="Add item from catalog..."),
                        dbc.Button("Add Item", id="btn-add", color="primary")
                    ], className="mb-3"),
                    html.Div(id="cart", className="mb-4"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col("Subtotal:", className="text-muted text-end", width=8),
                        dbc.Col(id="subtot-display", className="fw-bold text-end", width=4)
                    ]),
                    dbc.Row([
                        dbc.Col("Tax (8.25%):", className="text-muted text-end", width=8),
                        dbc.Col(id="tax-display", className="fw-bold text-end", width=4)
                    ]),
                    dbc.Row([
                        dbc.Col("TOTAL DUE:", className="fw-bold text-end fs-5 mt-2", width=8),
                        dbc.Col(id="tot", className="fw-bold text-end fs-5 mt-2 text-primary", width=4)
                    ]),
                    html.Div(id="q-acts", className="d-flex justify-content-end mt-4 gap-2"),
                    html.Div(id="q-toast")
                ], md=8, className="ps-4")
            ])
        ], className="saas-card")
    ])

def DispatchBoardView():
    # Fetch Data
    unassigned = get_df("SELECT j.id, c.name, j.total FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status = 'Unscheduled'")
    scheduled = get_df("SELECT j.*, c.name FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status IN ('Scheduled', 'Completed')")
    
    # Render Tech Lists
    techs = ["Elliott", "Sarah", "Mike", "John"]
    tech_columns = []
    
    for tech in techs:
        # Get jobs for this tech
        t_jobs = scheduled[scheduled['tech'] == tech]
        job_cards = []
        if t_jobs.empty:
            job_cards.append(html.Div("No jobs scheduled", className="text-muted small fst-italic mt-2"))
        else:
            for _, job in t_jobs.iterrows():
                job_cards.append(dbc.Card([
                    dbc.CardBody([
                        html.H6(job['name'], className="fw-bold mb-1"),
                        html.Small(f"Job #{job['id']} • {job['scheduled_date']}", className="text-muted")
                    ], className="p-2")
                ], className="mb-2 shadow-sm border-0 bg-light"))
        
        tech_columns.append(html.Div([
            html.Div([html.Div(tech[0], className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center me-2", style={"width":"32px","height":"32px"}), html.H6(tech, className="mb-0 fw-bold")], className="d-flex align-items-center mb-3 p-2 border-bottom"),
            html.Div(job_cards, className="p-2")
        ], className="mb-4"))

    return html.Div([
        html.H2("Dispatch Board", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([
                html.H5([html.I(className="bi bi-inbox me-2 text-danger"), "Unassigned"], className="fw-bold mb-3"),
                dash_table.DataTable(
                    id='u-table', data=unassigned.to_dict('records'), 
                    columns=[{"name":"Job","id":"id"},{"name":"Client","id":"name"}], 
                    row_selectable='single', style_as_list_view=True,
                    style_header={'display':'none'}, style_cell={'padding':'12px', 'borderBottom':'1px solid #eee'}
                ),
                html.Div(id="assign-trigger-placeholder", className="mt-3")
            ], className="saas-card h-100"), md=3),
            
            dbc.Col(html.Div([
                html.H5("Technician Schedule", className="fw-bold mb-3"),
                dbc.Row([dbc.Col(c, md=6) for c in tech_columns]) # 2x2 Grid of Techs
            ], className="saas-card h-100"), md=9)
        ]),
        dbc.Modal([
            dbc.ModalHeader("Assign Job"),
            dbc.ModalBody([
                dcc.Input(id="d-jid", type="hidden"),
                html.Label("Select Technician", className="fw-bold"),
                dbc.Select(id="d-tech", options=[{"label":t,"value":t} for t in techs], className="mb-3"),
                html.Label("Schedule Date", className="fw-bold"),
                dcc.DatePickerSingle(id="d-date", date=date.today(), display_format="YYYY-MM-DD", className="d-block w-100")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm Assignment", id="btn-d-ok", color="primary"))
        ], id="d-modal", is_open=False)
    ])

def JobView(jid):
    res = execute_query("SELECT j.*, c.name, c.address, c.phone FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.id = %s", (jid,), fetch=True)
    if not res: return html.Div("Job not found")
    job = res[0]
    items = json.loads(job['items_json'])
    
    return html.Div([
        dcc.Store(id="j-state", data={"id":jid, "items":items}),
        html.A([html.I(className="bi bi-arrow-left me-2"), "Back to Dispatch"], href="/dispatch", className="text-decoration-none text-muted mb-4 d-block"),
        
        dbc.Row([
            dbc.Col([
                html.H2(f"Job {jid}", className="fw-bold d-inline me-3"),
                html.Span(job['status'], className=f"badge-pill status-{job['status']}")
            ], width=8),
            dbc.Col(dbc.Button([html.I(className="bi bi-check-circle-fill me-2"), "Complete Job"], id="btn-j-comp", color="success", className="float-end"), width=4)
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6("CUSTOMER DETAILS", className="text-label mb-3"),
                    html.H4(job['name'], className="fw-bold"),
                    html.P(job['address'], className="text-muted mb-1"),
                    html.P([html.I(className="bi bi-telephone me-2"), job['phone']], className="text-muted"),
                    html.Hr(),
                    html.H6("DISPATCH NOTES", className="text-label mb-2"),
                    html.Div("Check in at back gate.", className="p-3 bg-light rounded text-muted small")
                ], className="saas-card mb-3"),
                
                html.Div([
                    html.Div([html.H6("WORK ORDER", className="text-label"), dbc.Button("+ Add Part", id="btn-j-add-modal", size="sm", color="link")], className="d-flex justify-content-between mb-3"),
                    html.Div(id="j-cart"),
                    html.Hr(),
                    html.H4(id="j-total", className="text-end fw-bold text-primary")
                ], className="saas-card")
            ], md=7),
            
            dbc.Col([
                html.Div([
                    dcc.Graph(figure=generate_map(), config={'displayModeBar': False})
                ], className="saas-card p-0 overflow-hidden")
            ], md=5)
        ]),
        
        dbc.Modal([
            dbc.ModalHeader("Add Part / Labor"),
            dbc.ModalBody([
                dbc.Input(id="j-add-n", placeholder="Description"),
                dbc.Input(id="j-add-p", placeholder="Price", type="number", className="mt-2")
            ]),
            dbc.ModalFooter(dbc.Button("Add", id="btn-j-add-confirm", color="primary"))
        ], id="j-modal", is_open=False)
    ])

# =========================================================
#  5. APP ROUTING & CALLBACKS
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
    if path == "/jobs": return QuotesListView() # Reusing for POC
    if path == "/accounts": return QuotesListView() # Reusing for POC
    if path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    if path.startswith("/job/"): return JobView(path.split("/")[-1])
    return DashboardView()

@app.callback([Output("url", "pathname"), Output("login-msg", "children")], Input("btn-login", "n_clicks"), [State("login-user", "value"), State("login-pass", "value")], prevent_initial_call=True)
def login_act(n, u, p):
    res = execute_query("SELECT id, password_hash, role FROM users WHERE username=%s", (u,), fetch=True)
    if res and check_password_hash(res[0]['password_hash'], p):
        login_user(User(res[0]['id'], u, res[0]['role']))
        return "/", ""
    return dash.no_update, "Invalid Username or Password"

@app.callback([Output("quote-state", "data"), Output("cart", "children"), Output("subtot-display", "children"), Output("tax-display", "children"), Output("tot", "children"), Output("q-acts", "children"), Output("dl-pdf", "data"), Output("q-toast", "children")], [Input("btn-add", "n_clicks"), Input({"type":"a-btn", "index":ALL}, "n_clicks")], [State("cat-sel", "value"), State("quote-state", "data"), State("c-sel", "value")])
def quote_logic(n_add, n_act, cat_id, state, cust_id):
    ctx_id = ctx.triggered_id
    pdf, toast = dash.no_update, None
    state['customer_id'] = cust_id
    
    if ctx_id == "btn-add" and cat_id:
        item = execute_query("SELECT * FROM catalog WHERE id=%s", (cat_id,), fetch=True)[0]
        state['items'].append({"name":item['name'], "qty":1, "price":item['price']})
    
    sub = sum(i['qty']*i['price'] for i in state['items'])
    tax = sub * 0.0825
    total = sub + tax
    state['total'] = total
    
    if isinstance(ctx_id, dict) and ctx_id['type'] == "a-btn":
        act = ctx_id['index']
        vals = (state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), json.dumps(state['items']), sub, tax, 0, 0, total, "")
        if act == "save":
            if state['id'] == "Q-NEW":
                state['id'] = f"Q-{random.randint(1000,9999)}"
                execute_query("INSERT INTO quotes VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (state['id'],)+vals)
            else:
                execute_query("UPDATE quotes SET customer_id=%s, status=%s, created_at=%s, items_json=%s, subtotal=%s, tax=%s, discount=%s, fee=%s, total=%s, notes=%s WHERE id=%s", vals+(state['id'],))
            toast = dbc.Toast("Quote saved successfully.", header="Saved", icon="success", duration=2000, style={"position":"fixed", "top":20, "right":20})
        elif act == "approve":
            execute_query("UPDATE quotes SET status='Approved' WHERE id=%s", (state['id'],))
            execute_query("INSERT INTO jobs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (f"J-{random.randint(1000,9999)}", state['id'], state['customer_id'], "Unscheduled", None, None, json.dumps(state['items']), "", total))
            state['status'] = "Approved"
            toast = dbc.Toast("Job created in Dispatch.", header="Approved", icon="success", duration=3000, style={"position":"fixed", "top":20, "right":20})
        elif act == "pdf":
            pdf = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")

    # Render Cart
    cart = [dbc.Row([
        dbc.Col([html.H6(i['name'], className="mb-0"), html.Small(f"${i['price']}", className="text-muted")], width=8),
        dbc.Col(html.H6(f"x{i['qty']}", className="mb-0 text-center"), width=2),
        dbc.Col(html.H6(f"${i['price']*i['qty']:.0f}", className="mb-0 text-end"), width=2)
    ], className="mb-3 border-bottom pb-2") for i in state['items']]
    
    btns = [dbc.Button("Save Draft", id={"type":"a-btn", "index":"save"}, color="light", className="border me-2"), dbc.Button("Download PDF", id={"type":"a-btn", "index":"pdf"}, color="light", className="border")]
    if state['status'] == "Draft": btns.append(dbc.Button("Approve Quote", id={"type":"a-btn", "index":"approve"}, color="success", className="ms-2"))
    
    return state, cart, f"${sub:,.2f}", f"${tax:,.2f}", f"${total:,.2f}", btns, pdf, toast

@app.callback([Output("d-modal", "is_open"), Output("d-jid", "value"), Output("url", "pathname", allow_duplicate=True)], [Input("u-table", "selected_rows"), Input("btn-d-ok", "n_clicks")], [State("u-table", "data"), State("d-jid", "value"), State("d-tech", "value"), State("d-date", "date")], prevent_initial_call=True)
def dispatch_logic(sel, ok, data, jid, tech, dt):
    if ctx.triggered_id == "u-table" and sel: return True, data[sel[0]]['id'], dash.no_update
    if ctx.triggered_id == "btn-d-ok":
        execute_query("UPDATE jobs SET status='Scheduled', tech=%s, scheduled_date=%s WHERE id=%s", (tech, dt, jid))
        return False, "", "/dispatch"
    return False, "", dash.no_update

@app.callback([Output("j-cart", "children"), Output("j-total", "children"), Output("j-state", "data"), Output("j-modal", "is_open")], [Input("btn-j-add-modal", "n_clicks"), Input("btn-j-add-confirm", "n_clicks"), Input("btn-j-comp", "n_clicks")], [State("j-add-n", "value"), State("j-add-p", "value"), State("j-state", "data")], prevent_initial_call=True)
def job_update(n_mod, n_add, n_comp, desc, price, state):
    if ctx.triggered_id == "btn-j-add-modal": return dash.no_update, dash.no_update, dash.no_update, True
    if ctx.triggered_id == "btn-j-add-confirm" and desc:
        state['items'].append({"name": desc, "qty": 1, "price": float(price or 0)})
    if ctx.triggered_id == "btn-j-comp":
        tot = sum(i['qty']*i['price'] for i in state['items'])
        execute_query("UPDATE jobs SET status='Completed', items_json=%s, total=%s WHERE id=%s", (json.dumps(state['items']), tot, state['id']))
    
    tot = sum(i['qty']*i['price'] for i in state['items'])
    cart = [dbc.Row([dbc.Col(i['name'], width=8), dbc.Col(f"${i['price']}", className="text-end fw-bold", width=4)], className="mb-2 border-bottom pb-2") for i in state['items']]
    return cart, f"Total: ${tot:,.2f}", state, False

@app.callback(Output("url", "pathname", allow_duplicate=True), Input("quotes-table", "selected_rows"), State("quotes-table", "data"), prevent_initial_call=True)
def nav_q(sel, data): return f"/builder/{data[sel[0]]['id']}"

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
