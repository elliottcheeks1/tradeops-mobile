import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import sqlite3
import json
import uuid
import random

# =========================================================
#   1. DATABASE LAYER (Schema V6 - Quotes vs Jobs)
# =========================================================
DB_FILE = "tradeops_production.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers 
                 (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, 
                  type TEXT, notes TEXT, created_at TEXT)''')
    
    # 2. Catalog
    c.execute('''CREATE TABLE IF NOT EXISTS catalog 
                 (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
    
    # 3. Quotes (The Proposal)
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, 
                  created_at TEXT, items_json TEXT, subtotal REAL, tax REAL, 
                  discount REAL, fee REAL, total REAL, notes TEXT)''')

    # 4. Jobs (The Execution - Linked to Quote)
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id TEXT PRIMARY KEY, quote_id TEXT, customer_id TEXT, status TEXT,
                  scheduled_date TEXT, tech TEXT, items_json TEXT, 
                  notes TEXT, total REAL)''')
    
    # Seed Data
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        print("Seeding Enterprise Data...")
        # Customers
        customers = [
            ("C-1", "Starbucks #402", "123 Latte Ln", "mgr@sbux.com", "555-0101", "Commercial", "Gate: 9999", datetime.now().isoformat()),
            ("C-2", "Hilton Hotel", "400 River St", "ap@hilton.com", "555-0102", "Commercial", "Check in at security", datetime.now().isoformat()),
            ("C-3", "Mike Anderson", "88 Suburbia Dr", "mike@gmail.com", "555-0199", "Residential", "Dog in yard", datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
        
        # Catalog
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0),
            ("F-1", "Permit Fee", "Fee", 0.0, 150.0),
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
#   2. THEME & CSS
# =========================================================
THEME = {
    "primary": "#2665EB", "secondary": "#6c757d", "success": "#00C853", 
    "warning": "#FFAB00", "danger": "#FF3D00", "bg_main": "#F4F7F6", "text": "#2c3e50"
}

custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; color: {THEME['text']}; }}
    .sidebar {{ position: fixed; top: 0; left: 0; bottom: 0; width: 260px; padding: 2rem 1.5rem; background: #fff; border-right: 1px solid #e0e0e0; z-index: 1000; overflow-y: auto; }}
    .content {{ margin-left: 260px; padding: 2rem; transition: 0.3s; }}
    @media (max-width: 768px) {{
        .sidebar {{ position: relative; width: 100%; height: auto; padding: 1rem; border-right: none; border-bottom: 1px solid #eee; display: flex; overflow-x: auto; white-space: nowrap; }}
        .content {{ margin-left: 0; padding: 1rem; }}
        .nav-link {{ margin-right: 15px; display: inline-block; }}
    }}
    .saas-card {{ background: #fff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #f0f0f0; }}
    .nav-link {{ color: #555; font-weight: 500; padding: 12px 15px; border-radius: 8px; transition: 0.2s; margin-bottom: 5px; display: flex; align-items: center; }}
    .nav-link:hover {{ background-color: #f8f9fa; color: {THEME['primary']}; }}
    .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; font-weight: 600; }}
    .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {{ background-color: #f8f9fa !important; font-weight: 600 !important; border-bottom: 2px solid #eee !important; color: #6c757d; text-transform: uppercase; font-size: 0.8rem; }}
    /* Status Pills */
    .status-pill {{ padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }}
    .status-Unscheduled {{ background-color: #ffeeba; color: #856404; }}
    .status-Scheduled {{ background-color: #cff4fc; color: #055160; }}
    .status-Completed {{ background-color: #d1e7dd; color: #0f5132; }}
"""

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
server = app.server
app.index_string = '''<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>''' + custom_css + '''</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>'''

# =========================================================
#   3. PDF ENGINE
# =========================================================
def create_pdf(data, doc_type="Quote"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(38, 101, 235) 
    pdf.cell(0, 10, "TradeOps", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, "Field Service Solutions", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"{doc_type} #: {data['id']}", ln=True)
    pdf.cell(0, 8, f"Date: {date.today()}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(110, 10, "Description", 0, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 0, 0, 'C', 1)
    pdf.cell(50, 10, "Total", 0, 1, 'R', 1)
    
    pdf.set_font("Arial", "", 10)
    items = data.get('items', [])
    for item in items:
        line_total = item['price'] * item['qty']
        pdf.cell(110, 10, str(item['name'])[:55], 0, 0)
        pdf.cell(30, 10, str(item['qty']), 0, 0, 'C')
        pdf.cell(50, 10, f"${line_total:,.2f}", 0, 1, 'R')
        
    pdf.ln(5)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(38, 101, 235)
    pdf.cell(140, 12, "Total Due:", 0, 0, 'R')
    pdf.cell(50, 12, f"${data.get('total', 0):,.2f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#   4. COMPONENTS
# =========================================================
def Sidebar():
    return html.Div([
        html.H3([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": THEME['primary'], "fontSize": "1.5rem"}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-3"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-grid-3x3-gap me-3"), "Dispatch Board"], href="/dispatch", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-3"), "Quotes"], href="/quotes", active="exact"),
            dbc.NavLink([html.I(className="bi bi-tools me-3"), "Jobs List"], href="/jobs", active="exact"),
            dbc.NavLink([html.I(className="bi bi-people me-3"), "Accounts"], href="/accounts", active="exact"),
            dbc.NavLink([html.I(className="bi bi-sliders me-3"), "Settings"], href="/settings", active="exact"),
        ], vertical=True, pills=True)
    ], className="sidebar")

# =========================================================
#   5. VIEWS
# =========================================================

def DashboardView():
    df_q = get_df("SELECT * FROM quotes")
    df_j = get_df("SELECT * FROM jobs")
    
    monthly_rev = df_q['total'].sum() # Simple sum for demo
    open_pipe = len(df_q[df_q['status'].isin(['Draft', 'Sent'])])
    active_jobs = len(df_j[df_j['status'].isin(['Scheduled', 'Unscheduled'])])
    
    return html.Div([
        html.H2("Executive Dashboard", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue", className="text-muted"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Open Quotes", className="text-muted"), html.H3(str(open_pipe), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Active Jobs", className="text-muted"), html.H3(str(active_jobs), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Tech Utilization"), dbc.Progress(value=75, color="primary", className="mt-2")], className="saas-card"), md=3),
        ]),
        dbc.Row([
            dbc.Col(html.Div([
                html.H5("Recent Activity", className="fw-bold mb-3"),
                html.P("Live feed of quotes and jobs would go here...", className="text-muted")
            ], className="saas-card h-100"), md=8),
            dbc.Col(html.Div([
                html.H5("Quick Actions", className="fw-bold mb-3"),
                dbc.Button("New Quote", href="/builder/Q-NEW", color="primary", className="w-100 mb-2"),
                dbc.Button("Dispatch Board", href="/dispatch", color="dark", outline=True, className="w-100")
            ], className="saas-card h-100"), md=4)
        ])
    ])

def DispatchBoardView():
    # 1. Unscheduled Jobs (Bucket)
    unassigned = get_df("SELECT j.id, c.name as customer, j.total FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status = 'Unscheduled'")
    
    # 2. Scheduled Jobs (Calendar)
    scheduled = get_df("SELECT j.*, c.name as customer FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.status IN ('Scheduled', 'Completed')")
    
    # Left Column: The Bucket
    bucket_content = html.Div("No unscheduled jobs.", className="text-muted small p-3")
    if not unassigned.empty:
        bucket_content = dash_table.DataTable(
            id='dispatch-bucket-table',
            columns=[{"name": "Job ID", "id": "id"}, {"name": "Customer", "id": "customer"}],
            data=unassigned.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold'},
            style_cell={'padding': '10px'}, row_selectable='single'
        )

    # Right Column: The Gantt
    chart = html.Div("No scheduled jobs.", className="text-center text-muted p-5")
    if not scheduled.empty:
        chart = dcc.Graph(
            id="dispatch-graph", 
            figure=px.timeline(scheduled, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="status", text="customer", title="Technician Schedule").update_layout(template="plotly_white", height=600).update_traces(width=0.5),
            config={'displayModeBar': False}
        )

    return html.Div([
        html.H2("Dispatch Command Center", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Unassigned Jobs", className="fw-bold mb-2 text-danger"),
                    html.P("Select a job to assign.", className="small text-muted"),
                    bucket_content
                ], className="saas-card h-100")
            ], md=3),
            dbc.Col([
                html.Div([
                    html.H5("Schedule", className="fw-bold mb-2"),
                    chart
                ], className="saas-card h-100")
            ], md=9)
        ]),
        
        # Dispatch Modal
        dbc.Modal([
            dbc.ModalHeader("Assign Job"),
            dbc.ModalBody([
                dcc.Input(id="dispatch-job-id", type="hidden"),
                html.H5(id="dispatch-job-label", className="mb-3"),
                dbc.Label("Technician"),
                dbc.Select(id="dispatch-tech", options=[{"label":t,"value":t} for t in ["Elliott","Sarah","Mike","John"]], className="mb-3"),
                dbc.Label("Date"),
                dcc.DatePickerSingle(id="dispatch-date", date=date.today(), display_format="YYYY-MM-DD", className="d-block mb-3")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm Assignment", id="btn-confirm-dispatch", color="primary"))
        ], id="modal-dispatch", is_open=False)
    ])

def QuoteBuilderView(quote_id=None):
    # State Logic
    state = {"id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], "subtotal": 0, "tax": 0, "discount": 0, "fee": 0, "total": 0, "notes": ""}
    
    if quote_id and quote_id != "Q-NEW":
        df = get_df("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        if not df.empty:
            row = df.iloc[0]
            try: items = json.loads(row['items_json'])
            except: items = []
            state = {
                "id": row['id'], "status": row['status'], "customer_id": row['customer_id'],
                "items": items, "subtotal": row['subtotal'], "tax": row['tax'], 
                "discount": row['discount'], "fee": row['fee'], "total": row['total'], "notes": row['notes']
            }

    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")

    return html.Div([
        dcc.Store(id="quote-state", data=state),
        dcc.Download(id="download-pdf"),
        dbc.Button("← Back to List", href="/quotes", color="link", className="mb-2 ps-0", style={"textDecoration": "none"}),
        
        dbc.Row([
            dbc.Col(html.H2(f"Quote: {state['id']}", className="fw-bold"), width=8),
            dbc.Col(html.Div(f"Status: {state['status']}", className="badge bg-secondary p-2 fs-6"), width=4, className="text-end")
        ]),

        dbc.Row([
            # Customer Info
            dbc.Col([
                html.Div([
                    html.H5("Customer", className="fw-bold mb-3"),
                    dcc.Dropdown(id="cust-select", options=[{'label': r['name'], 'value': r['id']} for _, r in customers.iterrows()], value=state['customer_id'], placeholder="Select..."),
                    html.Br(),
                    dbc.Label("Notes"),
                    dbc.Textarea(id="quote-notes", value=state['notes'], style={"height": "100px"}),
                    html.Hr(),
                    html.Div(id="action-buttons"), # Dynamic Buttons
                    html.Div(id="toast-container")
                ], className="saas-card h-100")
            ], md=4),

            # Line Items
            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold mb-3"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="catalog-select", options=[{'label': f"{r['name']} (${r['price']})", 'value': r['id']} for _, r in catalog.iterrows()], placeholder="Add Item..."), md=7),
                        dbc.Col(dbc.Input(id="item-qty", type="number", value=1, min=1), md=2),
                        dbc.Col(dbc.Button("Add", id="btn-add-item", color="primary", className="w-100"), md=3)
                    ], className="mb-3"),
                    
                    html.Div(id="cart-container", className="mb-4"),
                    html.Hr(),
                    
                    dbc.Row([
                        dbc.Col([dbc.Label("Discount"), dbc.Input(id="in-discount", type="number", value=state['discount'])], md=4),
                        dbc.Col([dbc.Label("Tax (8.25%)"), dbc.Input(id="in-tax", type="number", value=state['tax'], disabled=True)], md=4),
                        dbc.Col([dbc.Label("Fee"), dbc.Input(id="in-fee", type="number", value=state['fee'])], md=4),
                    ], className="mb-3"),
                    html.H2(id="total-display", className="fw-bold text-end text-success"),
                ], className="saas-card h-100")
            ], md=8)
        ])
    ])

def JobCommandCenter(job_id):
    # Load Job Data
    job = get_df("SELECT j.*, c.name, c.address FROM jobs j JOIN customers c ON j.customer_id = c.id WHERE j.id = ?", (job_id,))
    if job.empty: return html.Div("Job not found")
    job = job.iloc[0]
    
    # Parse Items
    try: items = json.loads(job['items_json'])
    except: items = []

    return html.Div([
        dcc.Store(id="job-state", data={"id": job_id, "items": items, "status": job['status']}),
        dcc.Download(id="download-job-pdf"),
        dbc.Button("← Back to Dispatch", href="/dispatch", color="link", className="mb-2 ps-0"),
        
        dbc.Row([
            dbc.Col([
                html.H2(f"Job: {job_id}", className="fw-bold"),
                html.Span(f"{job['status']}", className=f"status-pill status-{job['status']}")
            ], width=8),
            dbc.Col(dbc.Button("Complete & Invoice", id="btn-complete-job", color="success", className="float-end"), width=4)
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Job Info", className="fw-bold"),
                    html.P([html.I(className="bi bi-person me-2"), job['name']], className="mb-1"),
                    html.P([html.I(className="bi bi-geo-alt me-2"), job['address']], className="mb-1"),
                    html.P([html.I(className="bi bi-calendar me-2"), job['scheduled_date']], className="mb-1"),
                    html.P([html.I(className="bi bi-person-badge me-2"), job['tech']], className="mb-3"),
                    html.Hr(),
                    html.H6("Tech Notes"),
                    dbc.Textarea(id="job-notes", placeholder="Add notes from site...", value=job['notes'], style={"height": "150px"})
                ], className="saas-card h-100")
            ], md=4),
            
            dbc.Col([
                html.Div([
                    html.H5("Work Order (Edit Mode)", className="fw-bold mb-3"),
                    # Simplified Tech Editing (Add custom item only for speed)
                    dbc.Row([
                        dbc.Col(dbc.Input(id="tech-item-desc", placeholder="Part Name / Task..."), md=7),
                        dbc.Col(dbc.Input(id="tech-item-price", type="number", placeholder="Price"), md=3),
                        dbc.Col(dbc.Button("Add", id="btn-tech-add", color="secondary", className="w-100"), md=2)
                    ], className="mb-3"),
                    html.Div(id="job-items-container")
                ], className="saas-card h-100")
            ], md=8)
        ])
    ])

def QuotesListView():
    df = get_df("SELECT q.id, c.name, q.status, q.total, q.created_at FROM quotes q JOIN customers c ON q.customer_id = c.id ORDER BY q.created_at DESC")
    return html.Div([
        dbc.Row([dbc.Col(html.H2("Quotes", className="fw-bold"), width=10), dbc.Col(dbc.Button("+ Create", href="/builder/Q-NEW", color="primary"), width=2)]),
        html.Div(dash_table.DataTable(
            id='quotes-table',
            columns=[{"name": "ID", "id": "id"}, {"name": "Customer", "id": "name"}, {"name": "Status", "id": "status"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
            data=df.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '15px'}, row_selectable='single'
        ), className="saas-card")
    ])

def AccountsView():
    df = get_df("SELECT * FROM customers")
    return html.Div([
        dbc.Row([dbc.Col(html.H2("Accounts", className="fw-bold"), width=10), dbc.Col(dbc.Button("+ New", id="btn-new-acct", color="primary"), width=2)]),
        html.Div(dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{"name": "Name", "id": "name"}, {"name": "Type", "id": "type"}, {"name": "Address", "id": "address"}, {"name": "Phone", "id": "phone"}],
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '15px'}
        ), className="saas-card"),
        # Modal for New Account
        dbc.Modal([
            dbc.ModalHeader("New Account"),
            dbc.ModalBody([
                dbc.Input(id="new-acct-name", placeholder="Name"),
                dbc.Input(id="new-acct-addr", placeholder="Address", className="mt-2"),
                dbc.Input(id="new-acct-phone", placeholder="Phone", className="mt-2"),
            ]),
            dbc.ModalFooter(dbc.Button("Save", id="btn-save-acct", color="success"))
        ], id="modal-acct", is_open=False)
    ])

def SettingsView():
    df = get_df("SELECT * FROM catalog")
    return html.Div([
        html.H2("Settings", className="fw-bold mb-3"),
        html.Div(dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{"name": "Name", "id": "name"}, {"name": "Price", "id": "price", "type": "numeric", "format": {"specifier": "$,.2f"}}],
            style_as_list_view=True, style_header={'fontWeight': 'bold'}
        ), className="saas-card")
    ])

def JobsListView():
    df = get_df("SELECT j.id, c.name, j.status, j.scheduled_date, j.tech FROM jobs j JOIN customers c ON j.customer_id = c.id")
    return html.Div([
        html.H2("All Jobs", className="fw-bold mb-3"),
        html.Div(dash_table.DataTable(
            id="all-jobs-table",
            data=df.to_dict('records'),
            columns=[{"name": "ID", "id": "id"}, {"name": "Customer", "id": "name"}, {"name": "Status", "id": "status"}, {"name": "Date", "id": "scheduled_date"}, {"name": "Tech", "id": "tech"}],
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '15px'}, row_selectable='single'
        ), className="saas-card")
    ])

# =========================================================
#   6. ROUTING
# =========================================================
app.layout = html.Div([dcc.Location(id="url", refresh=False), Sidebar(), html.Div(id="page-content", className="content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def router(path):
    if path == "/quotes": return QuotesListView()
    if path == "/dispatch": return DispatchBoardView()
    if path == "/jobs": return JobsListView()
    if path == "/accounts": return AccountsView()
    if path == "/settings": return SettingsView()
    if path and path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    if path and path.startswith("/job/"): return JobCommandCenter(path.split("/")[-1])
    return DashboardView()

@app.callback(Output("url", "pathname"), 
              [Input("quotes-table", "selected_rows"), Input("dispatch-bucket-table", "selected_rows"), Input("dispatch-graph", "clickData"), Input("all-jobs-table", "selected_rows")],
              [State("quotes-table", "data"), State("dispatch-bucket-table", "data"), State("all-jobs-table", "data")])
def navigation(sel_q, sel_b, click_g, sel_j, d_q, d_b, d_j):
    ctx_id = ctx.triggered_id
    if ctx_id == "quotes-table" and sel_q: return f"/builder/{d_q[sel_q[0]]['id']}"
    if ctx_id == "all-jobs-table" and sel_j: return f"/job/{d_j[sel_j[0]]['id']}"
    # Dispatch Board Interaction handled by Modal, but Calendar clicks go to Job
    if ctx_id == "dispatch-graph" and click_g: return f"/job/{click_g['points'][0]['text']}" # Job ID stored in text
    return dash.no_update

# =========================================================
#   7. LOGIC CALLBACKS
# =========================================================

# --- QUOTE BUILDER: Add/Delete Items, Calculate, Save, Approve ---
@app.callback(
    [Output("quote-state", "data"), Output("cart-container", "children"), Output("total-display", "children"), 
     Output("action-buttons", "children"), Output("toast-container", "children"), Output("download-pdf", "data"), 
     Output("in-tax", "value")],
    [Input("btn-add-item", "n_clicks"), Input({"type": "q-del", "index": ALL}, "n_clicks"), 
     Input({"type": "action-btn", "index": ALL}, "n_clicks"), 
     Input("in-discount", "value"), Input("in-fee", "value"), Input("quote-notes", "value"), Input("cust-select", "value")],
    [State("catalog-select", "value"), State("item-qty", "value"), State("quote-state", "data")]
)
def quote_logic(n_add, n_del, n_act, disc, fee, notes, cust, cat_id, qty, state):
    ctx_id = ctx.triggered_id
    toast, pdf = None, dash.no_update
    
    # Update State
    state.update({"discount": disc or 0, "fee": fee or 0, "notes": notes or "", "customer_id": cust})

    # Add Item
    if ctx_id == "btn-add-item" and cat_id:
        item = get_df("SELECT * FROM catalog WHERE id=?", (cat_id,)).iloc[0]
        state['items'].append({"uuid": str(uuid.uuid4()), "id": item['id'], "name": item['name'], "qty": float(qty or 1), "price": item['price']})

    # Delete Item
    if isinstance(ctx_id, dict) and ctx_id['type'] == "q-del":
        state['items'] = [i for i in state['items'] if i['uuid'] != ctx_id['index']]

    # Calc
    subtotal = sum(i['qty']*i['price'] for i in state['items'])
    state['tax'] = round(subtotal * 0.0825, 2)
    state['subtotal'] = subtotal
    state['total'] = subtotal + state['tax'] + state['fee'] - state['discount']

    # Actions
    if isinstance(ctx_id, dict) and ctx_id['type'] == "action-btn":
        act = ctx_id['index']
        # Save Quote
        vals = (state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), 
                json.dumps(state['items']), state['subtotal'], state['tax'], state['discount'], state['fee'], state['total'], state['notes'])
        if state['id'] == "Q-NEW":
            state['id'] = f"Q-{random.randint(10000,99999)}"
            execute_query("INSERT INTO quotes (id, customer_id, status, created_at, items_json, subtotal, tax, discount, fee, total, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (state['id'],)+vals)
        else:
            execute_query("UPDATE quotes SET customer_id=?, status=?, created_at=?, items_json=?, subtotal=?, tax=?, discount=?, fee=?, total=?, notes=? WHERE id=?", vals+(state['id'],))
        
        toast = dbc.Toast("Saved", header="Success", duration=2000, icon="success", style={"position":"fixed", "top":10, "right":10})

        # Workflow: Send
        if act == "send":
            state['status'] = "Sent"
            execute_query("UPDATE quotes SET status='Sent' WHERE id=?", (state['id'],))
            pdf = dcc.send_bytes(create_pdf(state, "Quote"), f"Quote_{state['id']}.pdf")
        
        # Workflow: Approve -> Create Job
        elif act == "approve":
            state['status'] = "Approved"
            execute_query("UPDATE quotes SET status='Approved' WHERE id=?", (state['id'],))
            # Create Job Record
            job_id = f"J-{random.randint(10000,99999)}"
            execute_query("INSERT INTO jobs (id, quote_id, customer_id, status, items_json, total) VALUES (?,?,?,?,?,?)", 
                          (job_id, state['id'], state['customer_id'], "Unscheduled", json.dumps(state['items']), state['total']))
            toast = dbc.Toast(f"Job {job_id} Created!", header="Approved", duration=3000, icon="success", style={"position":"fixed", "top":10, "right":10})

    # Render
    cart = [dbc.Row([
        dbc.Col(i['name'], width=6),
        dbc.Col(f"x{i['qty']}", width=2),
        dbc.Col(f"${i['price']*i['qty']:.2f}", width=3),
        dbc.Col(dbc.Button("x", id={"type": "q-del", "index": i['uuid']}, size="sm", color="link", className="text-danger"), width=1)
    ], className="border-bottom py-2") for i in state['items']]

    # Dynamic Buttons
    btns = [dbc.Button("Save Draft", id={"type":"action-btn", "index":"save"}, color="secondary", outline=True, className="w-100 mb-2")]
    if state['status'] == "Draft": btns.append(dbc.Button("Send to Customer", id={"type":"action-btn", "index":"send"}, color="primary", className="w-100"))
    elif state['status'] == "Sent": btns.append(dbc.Button("Mark Approved", id={"type":"action-btn", "index":"approve"}, color="success", className="w-100"))
    elif state['status'] == "Approved": btns.append(dbc.Button("Job Created (See Dispatch)", disabled=True, color="warning", className="w-100"))

    return state, cart, f"${state['total']:,.2f}", btns, toast, pdf, state['tax']

# --- DISPATCH BOARD: Assign Job ---
@app.callback(
    [Output("modal-dispatch", "is_open"), Output("dispatch-job-id", "value"), Output("dispatch-job-label", "children"), Output("page-content", "children", allow_duplicate=True)],
    [Input("dispatch-bucket-table", "selected_rows"), Input("btn-confirm-dispatch", "n_clicks")],
    [State("dispatch-bucket-table", "data"), State("dispatch-job-id", "value"), State("dispatch-tech", "value"), State("dispatch-date", "date")],
    prevent_initial_call=True
)
def dispatch_logic(sel_row, n_confirm, bucket_data, job_id, tech, job_date):
    ctx_id = ctx.triggered_id
    if ctx_id == "dispatch-bucket-table" and sel_row:
        row = bucket_data[sel_row[0]]
        return True, row['id'], f"Assign Job: {row['id']}", dash.no_update
    
    if ctx_id == "btn-confirm-dispatch":
        execute_query("UPDATE jobs SET status='Scheduled', tech=?, scheduled_date=? WHERE id=?", (tech, job_date, job_id))
        return False, "", "", DispatchBoardView()
    
    return False, "", "", dash.no_update

# --- JOB COMMAND CENTER: Tech Adds Parts / Completes ---
@app.callback(
    [Output("job-state", "data"), Output("job-items-container", "children"), Output("page-content", "children", allow_duplicate=True)],
    [Input("btn-tech-add", "n_clicks"), Input("btn-complete-job", "n_clicks"), Input({"type": "j-del", "index": ALL}, "n_clicks")],
    [State("tech-item-desc", "value"), State("tech-item-price", "value"), State("job-state", "data"), State("job-notes", "value")],
    prevent_initial_call=True
)
def job_execution(n_add, n_comp, n_del, desc, price, state, notes):
    ctx_id = ctx.triggered_id
    
    # Add Item (Tech Mode)
    if ctx_id == "btn-tech-add" and desc and price:
        state['items'].append({"uuid": str(uuid.uuid4()), "name": desc, "qty": 1, "price": float(price)})
    
    # Delete
    if isinstance(ctx_id, dict) and ctx_id['type'] == "j-del":
        state['items'] = [i for i in state['items'] if i['uuid'] != ctx_id['index']]

    # Calculate Total
    total = sum(i['qty']*i['price'] for i in state['items'])
    
    # Complete
    if ctx_id == "btn-complete-job":
        execute_query("UPDATE jobs SET status='Completed', items_json=?, notes=?, total=? WHERE id=?", (json.dumps(state['items']), notes, total, state['id']))
        return state, dash.no_update, JobsListView() # Redirect to list

    # Render
    cart = [dbc.Row([
        dbc.Col(i['name'], width=7),
        dbc.Col(f"${i['price']:.2f}", width=3),
        dbc.Col(dbc.Button("x", id={"type": "j-del", "index": i['uuid']}, size="sm", color="danger", outline=True), width=2)
    ], className="border-bottom py-2") for i in state['items']]
    
    cart.append(html.H4(f"Total: ${total:,.2f}", className="text-end mt-3"))

    return state, cart, dash.no_update

# --- ACCOUNTS: Create ---
@app.callback(
    [Output("modal-acct", "is_open"), Output("url", "pathname", allow_duplicate=True)],
    [Input("btn-new-acct", "n_clicks"), Input("btn-save-acct", "n_clicks")],
    [State("new-acct-name", "value"), State("new-acct-addr", "value"), State("new-acct-phone", "value")],
    prevent_initial_call=True
)
def create_account(n_new, n_save, name, addr, phone):
    if ctx.triggered_id == "btn-new-acct": return True, dash.no_update
    if ctx.triggered_id == "btn-save-acct" and name:
        new_id = f"C-{random.randint(1000,9999)}"
        execute_query("INSERT INTO customers (id, name, address, phone) VALUES (?,?,?,?)", (new_id, name, addr, phone))
        return False, "/accounts" # Refresh
    return False, dash.no_update

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
