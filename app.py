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
import io
import random

# =========================================================
#   1. DATABASE LAYER (SQLite)
# =========================================================
DB_FILE = "tradeops_v2.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS customers 
                 (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, type TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS catalog 
                 (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, 
                  created_at TEXT, scheduled_date TEXT, tech TEXT, 
                  items_json TEXT, tax REAL, discount REAL, fee REAL, 
                  notes TEXT, total REAL)''')
    
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        customers = [
            ("C-1", "Burger King #402", "123 Whopper Ln", "bk@franchise.com", "555-0101", "Commercial"),
            ("C-2", "Marriott Downtown", "400 Congress Ave", "mgr@marriott.com", "555-0102", "Commercial"),
            ("C-3", "John Doe (Res)", "88 Maple Dr", "john@gmail.com", "555-0199", "Residential"),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)
        
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0),
            ("F-1", "Trip Charge", "Fee", 0.0, 79.0),
        ]
        c.executemany("INSERT INTO catalog VALUES (?,?,?,?,?)", catalog)
        
    conn.commit()
    conn.close()

init_db()

# DB Helpers
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
#   2. APP CONFIG & THEME
# =========================================================
THEME = {
    "primary": "#2665EB", "secondary": "#6c757d", "success": "#28a745",
    "bg_main": "#F4F7F6", "bg_card": "#FFFFFF", "text": "#2c3e50",
    "warning": "#ffc107", "danger": "#dc3545"
}

custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; color: {THEME['text']}; }}
    
    /* Desktop Sidebar (Default) */
    .sidebar {{ position: fixed; top: 0; left: 0; bottom: 0; width: 250px; padding: 2rem 1rem; background: #fff; border-right: 1px solid #eee; z-index: 1000; overflow-y: auto; }}
    .content {{ margin-left: 260px; padding: 2rem; transition: 0.3s; }}
    
    /* MOBILE OVERRIDES (Screens smaller than 768px) */
    @media (max-width: 768px) {{
        .sidebar {{ 
            position: relative; 
            width: 100%; 
            height: auto; 
            padding: 1rem; 
            border-right: none; 
            border-bottom: 2px solid #eee;
            display: flex;
            flex-direction: row;
            overflow-x: auto;
            white-space: nowrap;
        }}
        .content {{ margin-left: 0; padding: 1rem; }}
        .nav-link {{ display: inline-block; margin-right: 15px; }}
        .saas-card {{ padding: 1rem; }}
    }}

    .saas-card {{ background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #f0f0f0; }}
    
    /* Stepper */
    .stepper-item {{ text-align: center; position: relative; z-index: 1; }}
    .stepper-item.active .step-circle {{ background-color: {THEME['primary']}; color: white; border: none; }}
    .stepper-item.completed .step-circle {{ background-color: {THEME['success']}; color: white; border: none; }}
    .step-circle {{ width: 30px; height: 30px; border-radius: 50%; background: #eee; display: flex; align-items: center; justify-content: center; margin: 0 auto 5px auto; font-weight: bold; font-size: 12px; color: #777; }}
    
    /* Nav */
    .nav-link {{ color: #555; font-weight: 500; padding: 10px 15px; border-radius: 8px; transition: 0.2s; margin-bottom: 5px; }}
    .nav-link:hover, .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; }}
    .nav-link i {{ width: 20px; text-align: center; }}
    
    /* Tables */
    .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {{ background-color: #f8f9fa !important; font-weight: 600 !important; border-bottom: 2px solid #eee !important; }}
    .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td {{ border-bottom: 1px solid #eee !important; }}
"""

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
server = app.server

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>''' + custom_css + '''</style></head>
    <body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>
'''

# =========================================================
#   3. PDF GENERATOR
# =========================================================
def create_pdf(quote_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(38, 101, 235) 
    pdf.cell(0, 10, "TradeOps Field", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, f"Quote #{quote_data['id']} | Date: {date.today()}", ln=True)
    if quote_data.get('scheduled_date'):
        pdf.cell(0, 10, f"Scheduled Service: {quote_data['scheduled_date']}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 10, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Price", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", "", 10)
    for item in quote_data.get('items', []):
        pdf.cell(100, 10, item['name'], 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(60, 10, f"${item['price']}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 10, "TOTAL", 0, 0, 'R')
    pdf.cell(60, 10, f"${quote_data['total']:,.2f}", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#   4. COMPONENTS
# =========================================================

def Sidebar():
    return html.Div([
        html.H3([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": THEME['primary'], "fontSize": "1.5rem"}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-3"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-people me-3"), "Accounts"], href="/accounts", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-3"), "Quotes"], href="/pipeline", active="exact"),
            dbc.NavLink([html.I(className="bi bi-tools me-3"), "Jobs"], href="/jobs", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-week me-3"), "Schedule"], href="/schedule", active="exact"),
        ], vertical=True, pills=True)
    ], className="sidebar")

def JobStepper(status):
    steps = ["Draft", "Sent", "Approved", "Scheduled", "Invoiced", "Paid"]
    try: curr_idx = steps.index(status)
    except: curr_idx = 0
    cols = []
    for i, step in enumerate(steps):
        if i < curr_idx: cls, icon = "stepper-item completed", html.I(className="bi bi-check")
        elif i == curr_idx: cls, icon = "stepper-item active", str(i+1)
        else: cls, icon = "stepper-item", str(i+1)
        cols.append(dbc.Col(html.Div([html.Div(icon, className="step-circle"), html.Small(step, className="fw-bold")], className=cls)))
    return html.Div(dbc.Row(cols, className="g-0"), className="mb-4 pt-3 pb-3 border-bottom")

# =========================================================
#   5. VIEWS
# =========================================================

def DashboardView():
    df_quotes = get_df("SELECT * FROM quotes")
    df_quotes['created_at'] = pd.to_datetime(df_quotes['created_at'])
    
    monthly_rev = df_quotes[df_quotes['created_at'] >= (datetime.now() - timedelta(days=30))]['total'].sum()
    open_pipeline = df_quotes[df_quotes['status'].isin(['Draft', 'Sent', 'Approved'])]['total'].sum()
    jobs_scheduled = len(df_quotes[df_quotes['status'] == 'Scheduled'])
    
    if not df_quotes.empty:
        rev_trend = df_quotes.groupby('created_at')['total'].sum().reset_index()
        fig_trend = px.line(rev_trend, x='created_at', y='total', title="Revenue Trend (30 Days)", markers=True)
        fig_trend.update_layout(template="plotly_white", height=300, margin=dict(l=20,r=20,t=40,b=20))
        fig_trend.update_traces(line_color=THEME['primary'], line_width=3)
    else:
        fig_trend = {}

    pipeline_counts = df_quotes['status'].value_counts().reset_index()
    pipeline_counts.columns = ['Stage', 'Count']
    stage_order = ["Draft", "Sent", "Approved", "Scheduled", "Invoiced", "Paid"]
    fig_funnel = px.bar(pipeline_counts, x='Stage', y='Count', title="Pipeline Volume", 
                        category_orders={"Stage": stage_order}, color='Stage')
    fig_funnel.update_layout(template="plotly_white", height=300, showlegend=False, margin=dict(l=20,r=20,t=40,b=20))

    return html.Div([
        html.H2("Dashboard", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue MTD", className="text-muted"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Pipeline Value", className="text-muted"), html.H3(f"${open_pipeline:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Jobs Scheduled", className="text-muted"), html.H3(str(jobs_scheduled), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Goal Progress"), dbc.Progress(value=(monthly_rev/50000)*100, color="success", className="mt-2", style={"height": "10px"}), html.Small("Target: $50k", className="text-muted")], className="saas-card"), md=3),
        ], className="mb-2"),
        dbc.Row([
            dbc.Col(html.Div(dcc.Graph(figure=fig_trend, config={'displayModeBar': False}), className="saas-card h-100"), md=8),
            dbc.Col(html.Div(dcc.Graph(figure=fig_funnel, config={'displayModeBar': False}), className="saas-card h-100"), md=4),
        ])
    ])

def AccountsView():
    df = get_df("SELECT * FROM customers")
    return html.Div([
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Add New Account")),
            dbc.ModalBody([
                dbc.Label("Company / Name"),
                dbc.Input(id="new-cust-name", placeholder="e.g. Starbucks #505", className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Type"), dbc.Select(id="new-cust-type", options=[{"label": "Commercial", "value": "Commercial"}, {"label": "Residential", "value": "Residential"}], value="Commercial")], width=6),
                    dbc.Col([dbc.Label("Phone"), dbc.Input(id="new-cust-phone", placeholder="555-0000")], width=6)
                ], className="mb-3"),
                dbc.Label("Address"),
                dbc.Input(id="new-cust-address", placeholder="123 Main St...", className="mb-3"),
                dbc.Label("Email"),
                dbc.Input(id="new-cust-email", placeholder="billing@company.com"),
            ]),
            dbc.ModalFooter(dbc.Button("Save Account", id="btn-save-new-account", color="primary"))
        ], id="modal-new-account", is_open=False),

        dbc.Row([
            dbc.Col(html.H2("Accounts Directory", className="fw-bold"), width=9),
            dbc.Col(dbc.Button("+ New Account", id="btn-open-account-modal", color="primary", className="float-end"), width=3)
        ], className="mb-4"),
        
        html.Div([
            dash_table.DataTable(
                id='accounts-table',
                columns=[{"name": "Name", "id": "name"}, {"name": "Type", "id": "type"}, {"name": "Address", "id": "address"}, {"name": "Phone", "id": "phone"}],
                data=df.to_dict('records'),
                style_as_list_view=True,
                style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                style_cell={'padding': '15px', 'textAlign': 'left'},
                row_selectable='single',
                selected_rows=[]
            )
        ], className="saas-card")
    ])

def AccountDetailView(cust_id):
    cust = get_df("SELECT * FROM customers WHERE id = ?", (cust_id,)).iloc[0]
    history = get_df("SELECT * FROM quotes WHERE customer_id = ? ORDER BY created_at DESC", (cust_id,))
    
    return html.Div([
        dbc.Button("← Back to Accounts", href="/accounts", color="link", className="mb-3 ps-0"),
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.H2(cust['name'], className="fw-bold"),
                    dbc.Badge(cust['type'], color="info", className="me-2"),
                    html.Span([html.I(className="bi bi-geo-alt me-1"), cust['address']], className="text-muted me-3"),
                    html.Span([html.I(className="bi bi-telephone me-1"), cust['phone']], className="text-muted"),
                ], md=9),
                dbc.Col([
                    dbc.Button("Create Quote", href=f"/builder/new?cust={cust['id']}", color="primary", className="float-end")
                ], md=3)
            ])
        ], className="saas-card mb-4"),
        
        html.H4("History", className="fw-bold mb-3"),
        html.Div([
            dash_table.DataTable(
                columns=[{"name": "Quote ID", "id": "id"}, {"name": "Date", "id": "created_at"}, {"name": "Status", "id": "status"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
                data=history.to_dict('records'),
                style_as_list_view=True,
                style_cell={'padding': '10px', 'textAlign': 'left'},
                style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'}
            )
        ], className="saas-card")
    ])

def JobsView():
    df = get_df("SELECT q.id, c.name as customer, q.status, q.scheduled_date, q.tech, q.total FROM quotes q JOIN customers c ON q.customer_id = c.id WHERE q.status IN ('Scheduled', 'Invoiced', 'Paid') ORDER BY q.scheduled_date ASC")
    
    return html.Div([
        html.H2("Active Jobs", className="fw-bold mb-4"),
        html.Div([
            dash_table.DataTable(
                id='jobs-table',
                columns=[{"name": "Job ID", "id": "id"}, {"name": "Scheduled Date", "id": "scheduled_date"}, {"name": "Customer", "id": "customer"}, {"name": "Tech", "id": "tech"}, {"name": "Status", "id": "status"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
                data=df.to_dict('records'),
                style_as_list_view=True,
                style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                style_cell={'padding': '15px', 'textAlign': 'left'},
                style_data_conditional=[
                    {'if': {'filter_query': '{status} = "Scheduled"'}, 'backgroundColor': '#fff3cd', 'color': '#856404'},
                    {'if': {'filter_query': '{status} = "Paid"'}, 'backgroundColor': '#d1e7dd', 'color': '#0f5132'},
                ],
                row_selectable='single'
            )
        ], className="saas-card")
    ])

def PipelineView():
    df = get_df("SELECT q.id, c.name as customer, q.status, q.total, q.created_at, q.tech FROM quotes q JOIN customers c ON q.customer_id = c.id WHERE q.status IN ('Draft', 'Sent', 'Approved') ORDER BY q.created_at DESC")
    
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("Quote Pipeline", className="fw-bold"), width=9),
            dbc.Col(dbc.Button("+ New Quote", href="/builder/new", color="primary", className="float-end"), width=3)
        ], className="mb-4"),
        
        html.Div([
            dash_table.DataTable(
                id='pipeline-table',
                columns=[{"name": "ID", "id": "id"}, {"name": "Customer", "id": "customer"}, {"name": "Status", "id": "status"}, {"name": "Date", "id": "created_at"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
                data=df.to_dict('records'),
                style_as_list_view=True,
                style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                style_cell={'padding': '12px', 'textAlign': 'left'},
                row_selectable='single'
            )
        ], className="saas-card")
    ])

def QuoteBuilderView(quote_id=None):
    state = {"id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], "tax": 0, "discount": 0, "fee": 0, "notes": "", "tech": "Unassigned", "scheduled_date": None}
    
    if quote_id and quote_id != "new":
        df = get_df("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        if not df.empty:
            row = df.iloc[0]
            state = {
                "id": row['id'], "status": row['status'], "customer_id": row['customer_id'],
                "items": json.loads(row['items_json']), "tax": row['tax'], 
                "discount": row['discount'], "fee": row['fee'], "notes": row['notes'], 
                "tech": row['tech'], "scheduled_date": row['scheduled_date']
            }

    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")

    schedule_banner = html.Div()
    if state['scheduled_date']:
        schedule_banner = dbc.Alert([html.I(className="bi bi-calendar-check-fill me-2"), f"Service Scheduled: {state['scheduled_date']} with {state['tech']}"], color="success", className="mb-3 fw-bold")

    return html.Div([
        dcc.Store(id="quote-state", data=state),
        dcc.Download(id="download-pdf"),
        dbc.Button("← Back to Pipeline", href="/pipeline", color="link", className="mb-2 ps-0", style={"textDecoration": "none"}),
        
        dbc.Modal([
            dbc.ModalHeader("Convert to Job"),
            dbc.ModalBody([
                dbc.Label("Assign Technician"),
                dbc.Select(id="sched-tech", options=[{"label": t, "value": t} for t in ["Elliott", "Sarah", "Mike", "John"]]),
                html.Br(),
                dbc.Label("Select Service Date"),
                dcc.DatePickerSingle(id="sched-date", date=date.today(), display_format="YYYY-MM-DD", className="d-block mb-3")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm & Schedule", id="btn-confirm-schedule", color="primary"))
        ], id="modal-schedule", is_open=False),

        dbc.Row([dbc.Col([html.H2(f"Quote: {state['id']}", className="fw-bold"), schedule_banner], width=8), dbc.Col(html.Div(id="stepper-container"), width=12)]),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Customer Info", className="fw-bold mb-3"),
                    dcc.Dropdown(id="cust-select", options=[{'label': r['name'], 'value': r['id']} for _, r in customers.iterrows()], value=state['customer_id'], placeholder="Select Customer..."),
                    html.Br(),
                    dbc.Label("Internal Notes"),
                    dbc.Textarea(id="quote-notes", value=state['notes'], placeholder="Access codes, warnings...", style={"height": "100px"}),
                    html.Hr(),
                    html.H5("Actions", className="fw-bold mb-3"),
                    html.Div(id="action-buttons"),
                    html.Div(id="toast-container")
                ], className="saas-card h-100")
            ], md=4),

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
                        dbc.Col([dbc.Label("Discount ($)"), dbc.Input(id="in-discount", type="number", value=state['discount'])], md=4),
                        dbc.Col([dbc.Label("Tax ($)"), dbc.Input(id="in-tax", type="number", value=state['tax'])], md=4),
                        dbc.Col([dbc.Label("Trip Fee ($)"), dbc.Input(id="in-fee", type="number", value=state['fee'])], md=4),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(html.H4("Total", className="text-muted"), width=6),
                        dbc.Col(html.H2(id="total-display", className="fw-bold text-end text-success"), width=6),
                    ]),
                    html.Small(id="margin-display", className="text-muted float-end")
                ], className="saas-card h-100")
            ], md=8)
        ])
    ])

def ScheduleView():
    df = get_df("SELECT * FROM quotes WHERE status IN ('Scheduled', 'Invoiced', 'Paid')")
    chart = html.Div("No jobs scheduled yet.", className="text-center text-muted p-5")
    if not df.empty:
        chart = dcc.Graph(id="schedule-graph", figure=px.timeline(df, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="tech", text="id", title="Technician Schedule").update_layout(template="plotly_white", height=500).update_traces(width=0.5), config={'displayModeBar': False})
    
    return html.Div([html.H2("Dispatch Calendar", className="fw-bold mb-4"), html.Div(chart, className="saas-card")])

# =========================================================
#   6. MAIN LAYOUT & CALLBACKS
# =========================================================
app.layout = html.Div([dcc.Location(id="url", refresh=False), Sidebar(), html.Div(id="page-content", className="content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def router(path):
    if path == "/pipeline": return PipelineView()
    if path == "/jobs": return JobsView()
    if path == "/accounts": return AccountsView()
    if path == "/schedule": return ScheduleView()
    if path and path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    if path and path.startswith("/accounts/"): return AccountDetailView(path.split("/")[-1])
    return DashboardView()

@app.callback(Output("url", "pathname"), 
              [Input("pipeline-table", "selected_rows"), Input("jobs-table", "selected_rows"), Input("accounts-table", "selected_rows")],
              [State("pipeline-table", "data"), State("jobs-table", "data"), State("accounts-table", "data")])
def navigation(sel_pipe, sel_job, sel_acct, d_pipe, d_job, d_acct):
    ctx_id = ctx.triggered_id
    if ctx_id == "pipeline-table" and sel_pipe: return f"/builder/{d_pipe[sel_pipe[0]]['id']}"
    if ctx_id == "jobs-table" and sel_job: return f"/builder/{d_job[sel_job[0]]['id']}"
    if ctx_id == "accounts-table" and sel_acct: return f"/accounts/{d_acct[sel_acct[0]]['id']}"
    return dash.no_update

@app.callback(Output("url", "pathname", allow_duplicate=True), Input("schedule-graph", "clickData"), prevent_initial_call=True)
def navigate_schedule_click(clickData):
    if clickData: return f"/builder/{clickData['points'][0]['text']}"
    return dash.no_update

@app.callback(
    [Output("modal-new-account", "is_open"), Output("accounts-table", "data")],
    [Input("btn-open-account-modal", "n_clicks"), Input("btn-save-new-account", "n_clicks")],
    [State("modal-new-account", "is_open"), State("new-cust-name", "value"), State("new-cust-type", "value"),
     State("new-cust-address", "value"), State("new-cust-phone", "value"), State("new-cust-email", "value")])
def handle_new_account(n_open, n_save, is_open, name, c_type, addr, phone, email):
    ctx_id = ctx.triggered_id
    if ctx_id == "btn-open-account-modal": return True, dash.no_update
    if ctx_id == "btn-save-new-account" and name:
        new_id = f"C-{random.randint(1000, 9999)}"
        execute_query("INSERT INTO customers (id, name, address, email, phone, type) VALUES (?,?,?,?,?,?)", (new_id, name, addr or "", email or "", phone or "", c_type))
        return False, get_df("SELECT * FROM customers").to_dict('records')
    return is_open, dash.no_update

@app.callback(
    [Output("quote-state", "data"), Output("cart-container", "children"), Output("total-display", "children"), 
     Output("margin-display", "children"), Output("stepper-container", "children"), Output("action-buttons", "children"), 
     Output("modal-schedule", "is_open"), Output("toast-container", "children"), Output("download-pdf", "data"), Output("in-tax", "value")],
    [Input("btn-add-item", "n_clicks"), Input({"type": "btn-delete", "index": ALL}, "n_clicks"), Input({"type": "qty-input", "index": ALL}, "value"),
     Input({"type": "action-btn", "index": ALL}, "n_clicks"), Input("in-tax", "value"), Input("in-discount", "value"), Input("in-fee", "value"),
     Input("btn-confirm-schedule", "n_clicks"), Input("quote-notes", "value"), Input("cust-select", "value")],
    [State("catalog-select", "value"), State("item-qty", "value"), State("quote-state", "data"), State("sched-tech", "value"), State("sched-date", "date")])
def update_quote_logic(n_add, n_del, qty_values, n_action, tax, disc, fee, n_sched, notes, cust_id, cat_id, add_qty, state, sched_tech, sched_date):
    
    ctx_id = ctx.triggered_id
    toast = None
    pdf_download = dash.no_update
    
    state.update({'discount': disc or 0, 'fee': fee or 0, 'notes': notes or "", 'customer_id': cust_id})

    if ctx_id == "btn-add-item" and cat_id:
        catalog = get_df("SELECT * FROM catalog WHERE id = ?", (cat_id,)).iloc[0]
        state['items'].append({"uuid": str(uuid.uuid4()), "id": catalog['id'], "name": catalog['name'], "qty": float(add_qty or 1), "price": catalog['price'], "cost": catalog['cost']})

    if isinstance(ctx_id, dict) and ctx_id['type'] == "btn-delete":
        state['items'] = [i for i in state['items'] if i['uuid'] != ctx_id['index']]

    if isinstance(ctx_id, dict) and ctx_id['type'] == "qty-input":
        target_uuid = ctx_id['index']
        for input_obj in ctx.inputs_list[2]: 
            if input_obj['id']['index'] == target_uuid:
                for item in state['items']:
                    if item['uuid'] == target_uuid:
                        item['qty'] = float(input_obj['value'] or 0)
                        break
                break

    subtotal = sum(i['qty'] * i['price'] for i in state['items'])
    total_cost = sum(i['qty'] * i['cost'] for i in state['items'])
    state['tax'] = round(subtotal * 0.0825, 2)
    total = subtotal + state['fee'] + state['tax'] - state['discount']
    margin = total - total_cost
    state['total'] = total

    sched_modal_open = False
    
    def save_to_db():
        if state['id'] == "Q-NEW":
            new_id = f"Q-{random.randint(10000,99999)}"
            state['id'] = new_id
            execute_query("INSERT INTO quotes (id, customer_id, status, created_at, items_json, tax, discount, fee, notes, total, tech) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (new_id, state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), json.dumps(state['items']), state['tax'], state['discount'], state['fee'], state['notes'], state['total'], state['tech']))
        else:
            execute_query("UPDATE quotes SET status=?, items_json=?, tax=?, discount=?, fee=?, notes=?, total=?, tech=?, scheduled_date=? WHERE id=?",
                          (state['status'], json.dumps(state['items']), state['tax'], state['discount'], state['fee'], state['notes'], state['total'], state.get('tech'), state.get('scheduled_date'), state['id']))

    if isinstance(ctx_id, dict) and ctx_id['type'] == "action-btn":
        action = ctx_id['index']
        if action == "save":
            save_to_db()
            toast = dbc.Toast("Draft Saved", header="Success", duration=2000, icon="success", style={"position": "fixed", "top": 10, "right": 10})
        elif action == "send":
            state['status'] = "Sent"
            save_to_db()
            toast = dbc.Toast("Quote Sent", header="Success", duration=2000, icon="primary", style={"position": "fixed", "top": 10, "right": 10})
            pdf_download = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")
        elif action == "download":
            pdf_download = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")
        elif action == "approve":
            state['status'] = "Approved"
            save_to_db()
        elif action == "schedule_prompt":
            sched_modal_open = True
        elif action == "complete":
            state['status'] = "Paid"
            save_to_db()

    if ctx_id == "btn-confirm-schedule":
        state['status'] = "Scheduled"
        state['tech'] = sched_tech
        state['scheduled_date'] = sched_date
        save_to_db()
        sched_modal_open = False
        toast = dbc.Toast("Job Scheduled!", header="Success", duration=2000, icon="success", style={"position": "fixed", "top": 10, "right": 10})

    cart_rows = [dbc.Row([
        dbc.Col(item['name'], width=5),
        dbc.Col(dbc.Input(type="number", value=item['qty'], min=1, id={"type": "qty-input", "index": item['uuid']}, size="sm"), width=2),
        dbc.Col(f"${item['price']*item['qty']:.2f}", width=3),
        dbc.Col(dbc.Button("❌", id={"type": "btn-delete", "index": item['uuid']}, size="sm", color="link", className="text-danger p-0"), width=2, className="text-end"),
    ], className="border-bottom py-2 align-items-center") for item in state['items']]

    status = state['status']
    btn_props = {"style": {"width": "100%", "marginBottom": "5px"}}
    dl_btn = dbc.Button("Download PDF", id={"type": "action-btn", "index": "download"}, color="dark", outline=True, size="sm", className="mb-3 w-100")
    
    btns = []
    if status == "Draft":
        btns = [dbc.Button("Save Draft", id={"type": "action-btn", "index": "save"}, color="secondary", outline=True, **btn_props),
                dbc.Button("Send to Customer", id={"type": "action-btn", "index": "send"}, color="primary", **btn_props)]
    elif status == "Sent":
        btns = [dbc.Button("Mark Approved", id={"type": "action-btn", "index": "approve"}, color="success", **btn_props)]
    elif status == "Approved":
        btns = [dbc.Button("Schedule Job", id={"type": "action-btn", "index": "schedule_prompt"}, color="warning", **btn_props)]
    elif status == "Scheduled":
        btns = [dbc.Button("Complete & Invoice", id={"type": "action-btn", "index": "complete"}, color="success", **btn_props)]
    else:
        btns = [dbc.Button("Job Closed", disabled=True, color="secondary", **btn_props)]
    btns.append(dl_btn)

    return (state, cart_rows, f"${total:,.2f}", f"Est. Margin: ${margin:,.2f}", 
            JobStepper(status), btns, sched_modal_open, toast, pdf_download, state['tax'])

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
