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
#   1. MODERN DATABASE ARCHITECTURE (SQLite)
# =========================================================
DB_FILE = "tradeops_ultimate.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Customers: Expanded schema for CRM
    c.execute('''CREATE TABLE IF NOT EXISTS customers 
                 (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT, phone TEXT, 
                  type TEXT, notes TEXT, created_at TEXT)''')
    
    # Catalog: Price book for parts/labor
    c.execute('''CREATE TABLE IF NOT EXISTS catalog 
                 (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL, sku TEXT)''')
    
    # Quotes: The core transaction record
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, 
                  created_at TEXT, scheduled_date TEXT, tech TEXT, 
                  items_json TEXT, subtotal REAL, tax REAL, discount REAL, 
                  fee REAL, total REAL, notes TEXT)''')
    
    # Check if empty, then Seed
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        print("Seeding Database with Demo Data...")
        customers = [
            ("C-1", "Starbucks #402", "123 Latte Ln", "manager@starbucks.com", "555-0101", "Commercial", "Gate code: 9999", datetime.now().isoformat()),
            ("C-2", "Hilton Riverside", "400 River St", "accounts@hilton.com", "555-0102", "Commercial", "Check in at security", datetime.now().isoformat()),
            ("C-3", "Mike Anderson", "88 Suburbia Dr", "mike@gmail.com", "555-0199", "Residential", "Dog in backyard", datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
        
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0, "HVAC-001"),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0, "HVAC-002"),
            ("P-3", "Smart Thermostat", "Part", 120.0, 350.0, "ELEC-005"),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0, "LAB-001"),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0, "LAB-002"),
            ("F-1", "Permit Fee", "Fee", 0.0, 150.0, "FEE-001"),
        ]
        c.executemany("INSERT INTO catalog VALUES (?,?,?,?,?,?)", catalog)
        
    conn.commit()
    conn.close()

init_db()

# --- Advanced DB Helpers ---
def get_df(query, args=()):
    """Returns a Pandas DataFrame from a SQL query."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(query, conn, params=args)
    conn.close()
    return df

def execute_query(query, args=()):
    """Executes INSERT/UPDATE/DELETE queries."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, args)
    conn.commit()
    conn.close()

# =========================================================
#   2. VISUAL THEME & RESPONSIVE CSS
# =========================================================
THEME = {
    "primary": "#2665EB",    # Royal Blue
    "secondary": "#6c757d",  # Slate
    "success": "#00C853",    # Vibrant Green
    "warning": "#FFAB00",    # Amber
    "danger": "#FF3D00",     # Red
    "bg_main": "#F4F7F6",    # Light Grey
    "text": "#2c3e50"        # Dark Blue/Grey
}

custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; color: {THEME['text']}; }}
    
    /* Layout */
    .sidebar {{ 
        position: fixed; top: 0; left: 0; bottom: 0; width: 260px; 
        padding: 2rem 1.5rem; background: #fff; border-right: 1px solid #e0e0e0; z-index: 1000; 
        overflow-y: auto; box-shadow: 2px 0 5px rgba(0,0,0,0.02);
    }}
    .content {{ margin-left: 260px; padding: 2.5rem; transition: 0.3s; }}
    
    /* Mobile Responsiveness */
    @media (max-width: 768px) {{
        .sidebar {{ 
            position: relative; width: 100%; height: auto; 
            padding: 1rem; border-right: none; border-bottom: 1px solid #eee;
            display: flex; overflow-x: auto; white-space: nowrap; 
        }}
        .content {{ margin-left: 0; padding: 1rem; }}
        .nav-link {{ margin-right: 15px; display: inline-block; }}
    }}

    /* Modern Components */
    .saas-card {{ 
        background: #fff; border-radius: 12px; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06); 
        padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #f0f0f0; 
    }}
    
    .nav-link {{ 
        color: #555; font-weight: 500; padding: 12px 15px; border-radius: 8px; 
        transition: all 0.2s ease; margin-bottom: 8px; display: flex; align-items: center; 
    }}
    .nav-link:hover {{ background-color: #f8f9fa; color: {THEME['primary']}; transform: translateX(5px); }}
    .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; font-weight: 600; }}
    
    /* Stepper */
    .stepper-item {{ text-align: center; position: relative; z-index: 1; }}
    .stepper-item::before {{ 
        content: ''; position: absolute; top: 15px; left: -50%; width: 100%; height: 2px; 
        background: #eee; z-index: -1; 
    }}
    .stepper-item:first-child::before {{ content: none; }}
    .stepper-item.active .step-circle {{ background-color: {THEME['primary']}; color: white; border: none; box-shadow: 0 0 0 4px #eef4ff; }}
    .stepper-item.completed .step-circle {{ background-color: {THEME['success']}; color: white; border: none; }}
    .step-circle {{ 
        width: 32px; height: 32px; border-radius: 50%; background: #eee; 
        display: flex; align-items: center; justify-content: center; margin: 0 auto 8px auto; 
        font-weight: bold; font-size: 12px; color: #777; transition: all 0.3s;
    }}
    
    /* Tables */
    .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {{ 
        background-color: #f8f9fa !important; font-weight: 600 !important; 
        border-bottom: 2px solid #eee !important; color: #6c757d; text-transform: uppercase; font-size: 0.8rem;
    }}
"""

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
server = app.server

app.index_string = '''<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>''' + custom_css + '''</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>'''

# =========================================================
#   3. PDF ENGINE (Robust)
# =========================================================
def create_pdf(quote_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(38, 101, 235) 
    pdf.cell(0, 10, "TradeOps", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, "Field Service Solutions", ln=True)
    pdf.ln(10)
    
    # Meta Data
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Quote #: {quote_data['id']}", ln=True)
    pdf.cell(0, 8, f"Date: {date.today()}", ln=True)
    if quote_data.get('scheduled_date'):
        pdf.cell(0, 8, f"Service Date: {quote_data['scheduled_date']} (Tech: {quote_data['tech']})", ln=True)
    pdf.ln(10)
    
    # Table Header
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(110, 10, "Description", 0, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 0, 0, 'C', 1)
    pdf.cell(50, 10, "Total", 0, 1, 'R', 1)
    
    # Items
    pdf.set_font("Arial", "", 10)
    for item in quote_data.get('items', []):
        line_total = item['price'] * item['qty']
        pdf.cell(110, 10, str(item['name'])[:55], 0, 0)
        pdf.cell(30, 10, str(item['qty']), 0, 0, 'C')
        pdf.cell(50, 10, f"${line_total:,.2f}", 0, 1, 'R')
        
    pdf.ln(5)
    
    # Totals
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    def print_row(label, value, bold=False):
        pdf.set_font("Arial", "B" if bold else "", 11)
        pdf.cell(140, 8, label, 0, 0, 'R')
        pdf.cell(50, 8, value, 0, 1, 'R')

    print_row("Subtotal:", f"${quote_data.get('subtotal', 0):,.2f}")
    if quote_data.get('fee'): print_row("Fees:", f"${quote_data['fee']:,.2f}")
    if quote_data.get('discount'): print_row("Discount:", f"-${quote_data['discount']:,.2f}")
    if quote_data.get('tax'): print_row("Tax (8.25%):", f"${quote_data['tax']:,.2f}")
    
    pdf.ln(2)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(38, 101, 235)
    pdf.cell(140, 12, "Total Due:", 0, 0, 'R')
    pdf.cell(50, 12, f"${quote_data['total']:,.2f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#   4. UI COMPONENTS (Sidebar & Status)
# =========================================================
def Sidebar():
    return html.Div([
        html.H3([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps"], className="fw-bold mb-5", style={"color": THEME['primary'], "fontSize": "1.5rem"}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-3"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-check me-3"), "Schedule"], href="/schedule", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-3"), "Pipeline"], href="/pipeline", active="exact"),
            dbc.NavLink([html.I(className="bi bi-people me-3"), "Accounts"], href="/accounts", active="exact"),
            dbc.NavLink([html.I(className="bi bi-tools me-3"), "Jobs"], href="/jobs", active="exact"),
            dbc.NavLink([html.I(className="bi bi-sliders me-3"), "Settings"], href="/settings", active="exact"),
        ], vertical=True, pills=True)
    ], className="sidebar")

def JobStepper(status):
    steps = ["Draft", "Sent", "Approved", "Scheduled", "Paid"]
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
#   5. VIEWS (Dashboard, Pipeline, etc.)
# =========================================================

def DashboardView():
    df_quotes = get_df("SELECT * FROM quotes")
    df_quotes['created_at'] = pd.to_datetime(df_quotes['created_at'])
    
    monthly_rev = df_quotes[df_quotes['created_at'] >= (datetime.now() - timedelta(days=30))]['total'].sum()
    open_pipeline = df_quotes[df_quotes['status'].isin(['Draft', 'Sent', 'Approved'])]['total'].sum()
    jobs_scheduled = len(df_quotes[df_quotes['status'] == 'Scheduled'])
    
    # Financial Trend Chart
    if not df_quotes.empty:
        daily_rev = df_quotes.groupby('created_at')['total'].sum().reset_index()
        fig_trend = px.area(daily_rev, x='created_at', y='total', title="Revenue Trend (30 Days)", markers=True)
        fig_trend.update_layout(template="plotly_white", height=300, margin=dict(l=20,r=20,t=40,b=20))
        fig_trend.update_traces(line_color=THEME['primary'], fillcolor="rgba(38, 101, 235, 0.1)")
    else: fig_trend = {}

    return html.Div([
        html.H2("Business Insights", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue MTD", className="text-muted"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Pipeline Value", className="text-muted"), html.H3(f"${open_pipeline:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Jobs Scheduled", className="text-muted"), html.H3(str(jobs_scheduled), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Goal Progress"), dbc.Progress(value=(monthly_rev/50000)*100, color="success", className="mt-2", style={"height": "10px"}), html.Small("Target: $50k", className="text-muted")], className="saas-card"), md=3),
        ], className="mb-2"),
        html.Div(dcc.Graph(figure=fig_trend, config={'displayModeBar': False}), className="saas-card")
    ])

def ScheduleView():
    to_schedule = get_df("SELECT q.id, c.name as customer, q.total FROM quotes q JOIN customers c ON q.customer_id = c.id WHERE q.status = 'Approved'")
    calendar_data = get_df("SELECT q.*, c.name as customer FROM quotes q JOIN customers c ON q.customer_id = c.id WHERE q.status IN ('Scheduled', 'Invoiced', 'Paid')")
    
    list_view = html.Div("No approved quotes pending.", className="text-muted small p-3")
    if not to_schedule.empty:
        list_view = dash_table.DataTable(
            id='unscheduled-table',
            columns=[{"name": "Quote ID", "id": "id"}, {"name": "Customer", "id": "customer"}],
            data=to_schedule.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold'},
            style_cell={'padding': '10px'}, row_selectable='single'
        )

    chart = html.Div("No jobs on calendar.", className="text-center text-muted p-5")
    if not calendar_data.empty:
        chart = dcc.Graph(
            id="schedule-graph", 
            figure=px.timeline(calendar_data, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="tech", text="customer", title="Technician Schedule").update_layout(template="plotly_white", height=600).update_traces(width=0.5),
            config={'displayModeBar': False}
        )

    return html.Div([
        html.H2("Dispatch Board", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("To Schedule", className="fw-bold mb-3 text-danger"),
                    html.P("Select a quote to dispatch.", className="small text-muted"),
                    list_view
                ], className="saas-card h-100")
            ], md=3),
            dbc.Col([
                html.Div([
                    html.H5("Calendar", className="fw-bold mb-3"),
                    html.Small("Click a job to edit or reschedule.", className="text-muted"),
                    chart
                ], className="saas-card h-100")
            ], md=9)
        ]),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Dispatch Job")),
            dbc.ModalBody([
                dcc.Input(id="dispatch-quote-id", type="hidden"),
                html.H5(id="dispatch-label", className="mb-3"),
                dbc.Label("Assign Technician"),
                dbc.Select(id="dispatch-tech", options=[{"label":t,"value":t} for t in ["Elliott","Sarah","Mike","John"]], className="mb-3"),
                dbc.Label("Select Date"),
                dcc.DatePickerSingle(id="dispatch-date", date=date.today(), display_format="YYYY-MM-DD", className="d-block mb-3")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm Schedule", id="btn-save-dispatch", color="primary"))
        ], id="modal-dispatch", is_open=False)
    ])

def QuoteBuilderView(quote_id=None):
    # Initialize State
    state = {
        "id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], 
        "subtotal": 0, "tax": 0, "discount": 0, "fee": 0, "total": 0,
        "notes": "", "tech": "Unassigned", "scheduled_date": None
    }
    
    # Load Data if Editing
    if quote_id and quote_id != "Q-NEW":
        df = get_df("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        if not df.empty:
            row = df.iloc[0]
            try: items = json.loads(row['items_json'])
            except: items = []
            state = {
                "id": row['id'], "status": row['status'], "customer_id": row['customer_id'],
                "items": items, "subtotal": row['subtotal'], "tax": row['tax'], 
                "discount": row['discount'], "fee": row['fee'], "total": row['total'],
                "notes": row['notes'], "tech": row['tech'], "scheduled_date": row['scheduled_date']
            }

    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")

    banner = html.Div()
    if state['status'] == 'Scheduled':
        banner = dbc.Alert([html.I(className="bi bi-calendar-check me-2"), f"Active Job: {state['scheduled_date']} ({state['tech']})"], color="success", className="fw-bold mb-3")

    return html.Div([
        dcc.Store(id="quote-state", data=state),
        dcc.Download(id="download-pdf"),
        dbc.Button("← Back to Pipeline", href="/pipeline", color="link", className="mb-2 ps-0", style={"textDecoration": "none"}),
        
        dbc.Row([dbc.Col([html.H2(f"Quote: {state['id']}", className="fw-bold"), banner], width=8), dbc.Col(html.Div(id="stepper-container"), width=12)]),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Customer", className="fw-bold mb-3"),
                    dcc.Dropdown(id="cust-select", options=[{'label': r['name'], 'value': r['id']} for _, r in customers.iterrows()], value=state['customer_id'], placeholder="Select..."),
                    html.Br(),
                    dbc.Label("Service Address"),
                    dbc.Input(id="service-address", placeholder="Auto-fills...", disabled=True, className="mb-2 bg-light"),
                    dbc.Label("Notes"),
                    dbc.Textarea(id="quote-notes", value=state['notes'], style={"height": "100px"}),
                    html.Hr(),
                    html.H5("Actions", className="fw-bold mb-3"),
                    html.Div(id="action-buttons"),
                    html.Div(id="toast-container")
                ], className="saas-card h-100")
            ], md=4),

            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold mb-3"),
                    # Catalog Add
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="catalog-select", options=[{'label': f"{r['name']} (${r['price']})", 'value': r['id']} for _, r in catalog.iterrows()], placeholder="Add Catalog Item..."), md=7),
                        dbc.Col(dbc.Input(id="item-qty", type="number", value=1, min=1), md=2),
                        dbc.Col(dbc.Button("Add", id="btn-add-item", color="primary", className="w-100"), md=3)
                    ], className="mb-2"),
                    
                    # Custom Add (Collapse)
                    dbc.Collapse(
                        dbc.Row([
                            dbc.Col(dbc.Input(id="custom-name", placeholder="Or Custom Item Name..."), md=7),
                            dbc.Col(dbc.Input(id="custom-price", type="number", placeholder="Price"), md=2),
                            dbc.Col(dbc.Button("Add Custom", id="btn-add-custom", color="secondary", outline=True, className="w-100"), md=3),
                        ], className="mb-3"), is_open=True
                    ),

                    html.Div(id="cart-container", className="mb-4"),
                    html.Hr(),
                    
                    # Financials
                    dbc.Row([
                        dbc.Col([dbc.Label("Discount"), dbc.Input(id="in-discount", type="number", value=state['discount'])], md=4),
                        dbc.Col([dbc.Label("Tax (8.25%)"), dbc.Input(id="in-tax", type="number", value=state['tax'], disabled=True)], md=4),
                        dbc.Col([dbc.Label("Fee"), dbc.Input(id="in-fee", type="number", value=state['fee'])], md=4),
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

def AccountsView():
    df = get_df("SELECT * FROM customers")
    return html.Div([
        dbc.Modal([
            dbc.ModalHeader("Edit Account"),
            dbc.ModalBody([
                dcc.Input(id="edit-cust-id", type="hidden"),
                dbc.Label("Name"), dbc.Input(id="edit-cust-name", className="mb-2"),
                dbc.Label("Address"), dbc.Input(id="edit-cust-address", className="mb-2"),
                dbc.Label("Phone"), dbc.Input(id="edit-cust-phone", className="mb-2"),
                dbc.Label("Email"), dbc.Input(id="edit-cust-email", className="mb-2"),
                dbc.Label("Notes"), dbc.Textarea(id="edit-cust-notes"),
            ]),
            dbc.ModalFooter(dbc.Button("Save Changes", id="btn-save-account", color="success"))
        ], id="modal-account", is_open=False),

        dbc.Row([
            dbc.Col(html.H2("Accounts", className="fw-bold"), width=9),
            dbc.Col(dbc.Button("+ New Account", id="btn-new-account", color="primary", className="float-end"), width=3)
        ], className="mb-4"),
        
        html.Div(dash_table.DataTable(
            id='accounts-table',
            columns=[{"name": "Name", "id": "name"}, {"name": "Address", "id": "address"}, {"name": "Phone", "id": "phone"}],
            data=df.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '15px'}, row_selectable='single'
        ), className="saas-card")
    ])

def PipelineView():
    df = get_df("SELECT q.id, c.name as customer, q.status, q.total, q.created_at, q.tech FROM quotes q JOIN customers c ON q.customer_id = c.id ORDER BY q.created_at DESC")
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("Quotes & Jobs", className="fw-bold"), width=9),
            dbc.Col(dbc.Button("+ New Quote", href="/builder/Q-NEW", color="primary", className="float-end"), width=3)
        ], className="mb-4"),
        html.Div(dash_table.DataTable(
            id='pipeline-table',
            columns=[{"name": "ID", "id": "id"}, {"name": "Customer", "id": "customer"}, {"name": "Status", "id": "status"}, {"name": "Date", "id": "created_at"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
            data=df.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '12px'}, row_selectable='single'
        ), className="saas-card")
    ])

def SettingsView():
    cat = get_df("SELECT * FROM catalog")
    return html.Div([
        html.H2("Settings & Catalog", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Add Item", className="fw-bold mb-3"),
                    dbc.Input(id="new-cat-name", placeholder="Item Name", className="mb-2"),
                    dbc.Select(id="new-cat-type", options=[{"label": "Part", "value": "Part"}, {"label": "Labor", "value": "Labor"}], value="Part", className="mb-2"),
                    dbc.Input(id="new-cat-price", type="number", placeholder="Price ($)", className="mb-2"),
                    dbc.Button("Add to Catalog", id="btn-save-catalog", color="primary", className="w-100")
                ], className="saas-card")
            ], md=4),
            dbc.Col([
                html.Div([
                    html.H5("Price Book", className="fw-bold mb-3"),
                    dash_table.DataTable(data=cat.to_dict('records'), columns=[{"name": "Name", "id": "name"}, {"name": "Price", "id": "price", "type": "numeric", "format": {"specifier": "$,.2f"}}], style_header={'fontWeight': 'bold'})
                ], className="saas-card")
            ], md=8)
        ])
    ])

def JobsView():
    df = get_df("SELECT q.id, c.name as customer, q.status, q.scheduled_date, q.tech, q.total FROM quotes q JOIN customers c ON q.customer_id = c.id WHERE q.status IN ('Scheduled', 'Invoiced', 'Paid') ORDER BY q.scheduled_date ASC")
    return html.Div([
        html.H2("Active Jobs", className="fw-bold mb-4"),
        html.Div(dash_table.DataTable(
            id='jobs-table',
            columns=[{"name": "Job ID", "id": "id"}, {"name": "Date", "id": "scheduled_date"}, {"name": "Customer", "id": "customer"}, {"name": "Status", "id": "status"}, {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}}],
            data=df.to_dict('records'),
            style_as_list_view=True, style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_cell={'padding': '15px'}, row_selectable='single'
        ), className="saas-card")
    ])

# =========================================================
#   6. ROUTER
# =========================================================
app.layout = html.Div([dcc.Location(id="url", refresh=False), Sidebar(), html.Div(id="page-content", className="content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def router(path):
    if path == "/pipeline": return PipelineView()
    if path == "/accounts": return AccountsView()
    if path == "/schedule": return ScheduleView()
    if path == "/settings": return SettingsView()
    if path == "/jobs": return JobsView()
    if path and path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    return DashboardView()

@app.callback(Output("url", "pathname"), 
              [Input("pipeline-table", "selected_rows"), Input("unscheduled-table", "selected_rows"), Input("jobs-table", "selected_rows")],
              [State("pipeline-table", "data"), State("unscheduled-table", "data"), State("jobs-table", "data")])
def nav_click(sel_pipe, sel_unsch, sel_job, d_pipe, d_unsch, d_job):
    ctx_id = ctx.triggered_id
    if ctx_id == "pipeline-table" and sel_pipe: return f"/builder/{d_pipe[sel_pipe[0]]['id']}"
    if ctx_id == "jobs-table" and sel_job: return f"/builder/{d_job[sel_job[0]]['id']}"
    # Unscheduled table navigation handled by dispatch modal, so ignore
    return dash.no_update

# =========================================================
#   7. COMPLEX LOGIC CALLBACKS
# =========================================================

# --- Schedule Logic (Dispatch & Reschedule) ---
@app.callback(
    [Output("modal-dispatch", "is_open"), Output("dispatch-label", "children"), Output("dispatch-quote-id", "value"), Output("page-content", "children", allow_duplicate=True), Output("url", "pathname", allow_duplicate=True)],
    [Input("unscheduled-table", "selected_rows"), Input("schedule-graph", "clickData"), Input("btn-save-dispatch", "n_clicks")],
    [State("unscheduled-table", "data"), State("dispatch-tech", "value"), State("dispatch-date", "date"), State("dispatch-quote-id", "value")],
    prevent_initial_call=True
)
def manage_schedule(sel_rows, graph_click, n_save, unsch_data, tech, job_date, quote_id):
    ctx_id = ctx.triggered_id
    
    if ctx_id == "unscheduled-table" and sel_rows:
        row = unsch_data[sel_rows[0]]
        return True, f"Dispatching: {row['customer']}", row['id'], dash.no_update, dash.no_update

    if ctx_id == "schedule-graph" and graph_click:
        q_id = graph_click['points'][0]['text']
        return False, "", "", dash.no_update, f"/builder/{q_id}"

    if ctx_id == "btn-save-dispatch":
        execute_query("UPDATE quotes SET status='Scheduled', tech=?, scheduled_date=? WHERE id=?", (tech, job_date, quote_id))
        return False, "", "", ScheduleView(), dash.no_update

    return False, "", "", dash.no_update, dash.no_update

# --- Account Logic (Create & Edit) ---
@app.callback(
    [Output("modal-account", "is_open"), Output("accounts-table", "data")],
    [Input("btn-new-account", "n_clicks"), Input("btn-save-account", "n_clicks"), Input("accounts-table", "selected_rows")],
    [State("modal-account", "is_open"), State("edit-cust-name", "value"), State("edit-cust-address", "value"), 
     State("edit-cust-phone", "value"), State("edit-cust-email", "value"), State("edit-cust-notes", "value"),
     State("edit-cust-id", "value"), State("accounts-table", "data")],
    prevent_initial_call=True
)
def manage_accounts(n_new, n_save, sel_row, is_open, name, addr, phone, email, notes, cust_id, table_data):
    ctx_id = ctx.triggered_id
    
    if ctx_id == "btn-new-account":
        return True, dash.no_update
    
    if ctx_id == "accounts-table" and sel_row:
        # Load data into modal (Simplified: In real app use separate callback to avoid loop)
        return True, dash.no_update 

    if ctx_id == "btn-save-account" and name:
        if cust_id: # Update
            execute_query("UPDATE customers SET name=?, address=?, phone=?, email=?, notes=? WHERE id=?", (name, addr, phone, email, notes, cust_id))
        else: # Insert
            new_id = f"C-{random.randint(1000,9999)}"
            execute_query("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", (new_id, name, addr, email, phone, "Commercial", notes or ""))
        return False, get_df("SELECT * FROM customers").to_dict('records')

    return is_open, dash.no_update

@app.callback(
    [Output("edit-cust-id", "value"), Output("edit-cust-name", "value"), Output("edit-cust-address", "value"), 
     Output("edit-cust-phone", "value"), Output("edit-cust-email", "value"), Output("edit-cust-notes", "value")],
    Input("accounts-table", "selected_rows"),
    State("accounts-table", "data"),
    prevent_initial_call=True
)
def load_account_form(sel_row, data):
    if sel_row:
        row = data[sel_row[0]]
        # Fetch full details
        full = get_df("SELECT * FROM customers WHERE id=?", (row['id'],)).iloc[0]
        return full['id'], full['name'], full['address'], full['phone'], full['email'], full['notes']
    return dash.no_update

# --- Catalog Logic ---
@app.callback(
    [Output("new-cat-name", "value"), Output("new-cat-price", "value")],
    Input("btn-save-catalog", "n_clicks"),
    [State("new-cat-name", "value"), State("new-cat-type", "value"), State("new-cat-price", "value")],
    prevent_initial_call=True
)
def save_catalog_item(n, name, type, price):
    if name and price:
        new_id = f"{type[0]}-{random.randint(100,999)}"
        execute_query("INSERT INTO catalog VALUES (?,?,?,?,?)", (new_id, name, type, 0.0, float(price)))
        return "", ""
    return dash.no_update, dash.no_update

# --- Address Autofill ---
@app.callback(Output("service-address", "value"), Input("cust-select", "value"))
def fill_addr(cid):
    if not cid: return ""
    df = get_df("SELECT address FROM customers WHERE id=?", (cid,))
    return df.iloc[0]['address'] if not df.empty else ""

# --- Master Quote Logic ---
@app.callback(
    [Output("quote-state", "data"), Output("cart-container", "children"), Output("total-display", "children"), 
     Output("margin-display", "children"), Output("stepper-container", "children"), Output("action-buttons", "children"), 
     Output("toast-container", "children"), Output("download-pdf", "data"), 
     Output("in-tax", "value"), Output("custom-name", "value"), Output("custom-price", "value")],
    [Input("btn-add-item", "n_clicks"), Input("btn-add-custom", "n_clicks"), Input({"type": "btn-delete", "index": ALL}, "n_clicks"), 
     Input({"type": "qty-input", "index": ALL}, "value"), Input({"type": "action-btn", "index": ALL}, "n_clicks"), 
     Input("in-tax", "value"), Input("in-discount", "value"), Input("in-fee", "value"),
     Input("quote-notes", "value"), Input("cust-select", "value")],
    [State("catalog-select", "value"), State("item-qty", "value"), State("custom-name", "value"), State("custom-price", "value"),
     State("quote-state", "data")])
def update_quote_logic(n_add, n_custom, n_del, qty_values, n_action, tax, disc, fee, notes, cust_id, 
                       cat_id, add_qty, c_name, c_price, state):
    ctx_id = ctx.triggered_id
    toast, pdf_download = None, dash.no_update
    c_name_res, c_price_res = dash.no_update, dash.no_update
    
    state.update({'discount': disc or 0, 'fee': fee or 0, 'notes': notes or "", 'customer_id': cust_id})

    # Add Items
    if ctx_id == "btn-add-item" and cat_id:
        row = get_df("SELECT * FROM catalog WHERE id = ?", (cat_id,)).iloc[0]
        state['items'].append({"uuid": str(uuid.uuid4()), "id": row['id'], "name": row['name'], "qty": float(add_qty or 1), "price": row['price'], "cost": row['cost']})
    if ctx_id == "btn-add-custom" and c_name and c_price:
        state['items'].append({"uuid": str(uuid.uuid4()), "id": "CUSTOM", "name": c_name, "qty": 1.0, "price": float(c_price), "cost": 0.0})
        c_name_res, c_price_res = "", ""

    # Delete
    if isinstance(ctx_id, dict) and ctx_id['type'] == "btn-delete":
        state['items'] = [i for i in state['items'] if i['uuid'] != ctx_id['index']]

    # Update Qty
    if isinstance(ctx_id, dict) and ctx_id['type'] == "qty-input":
        for input_obj in ctx.inputs_list[3]:
            if input_obj['id']['index'] == ctx_id['index']:
                for item in state['items']:
                    if item['uuid'] == ctx_id['index']: item['qty'] = float(input_obj['value'] or 0)

    # Financials
    subtotal = sum(i['qty'] * i['price'] for i in state['items'])
    state['subtotal'] = subtotal
    state['tax'] = round(subtotal * 0.0825, 2)
    total = subtotal + state['fee'] + state['tax'] - state['discount']
    margin = total - sum(i['qty'] * i['cost'] for i in state['items'])
    state['total'] = total

    # Save
    def save_to_db():
        vals = (state['customer_id'], state['status'], date.today().strftime("%Y-%m-%d"), 
                state['scheduled_date'], state['tech'], json.dumps(state['items']), 
                state['tax'], state['discount'], state['fee'], state['notes'], state['total'])
        
        if state['id'] == "Q-NEW":
            new_id = f"Q-{random.randint(10000,99999)}"
            state['id'] = new_id
            execute_query("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (new_id,) + vals)
        else:
            execute_query("UPDATE quotes SET customer_id=?, status=?, created_at=?, scheduled_date=?, tech=?, items_json=?, tax=?, discount=?, fee=?, notes=?, total=? WHERE id=?", vals + (state['id'],))

    # Actions
    if isinstance(ctx_id, dict) and ctx_id['type'] == "action-btn":
        action = ctx_id['index']
        if action == "save": save_to_db(); toast = dbc.Toast("Saved", header="Success", duration=2000, icon="success", style={"position": "fixed", "top": 10, "right": 10})
        elif action == "send": state['status'] = "Sent"; save_to_db(); pdf_download = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")
        elif action == "download": pdf_download = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")
        elif action == "approve": state['status'] = "Approved"; save_to_db()
        elif action == "complete": state['status'] = "Paid"; save_to_db()

    # Render UI
    cart = [dbc.Row([
        dbc.Col(i['name'], width=5),
        dbc.Col(dbc.Input(type="number", value=i['qty'], min=1, id={"type": "qty-input", "index": i['uuid']}, size="sm"), width=2),
        dbc.Col(f"${i['price']*i['qty']:.2f}", width=3),
        dbc.Col(dbc.Button("❌", id={"type": "btn-delete", "index": i['uuid']}, size="sm", color="link", className="text-danger p-0"), width=2, className="text-end"),
    ], className="border-bottom py-2 align-items-center") for i in state['items']]

    status = state['status']
    btn_props = {"style": {"width": "100%", "marginBottom": "5px"}}
    dl_btn = dbc.Button("Download PDF", id={"type": "action-btn", "index": "download"}, color="dark", outline=True, size="sm", className="mb-3 w-100")
    btns = []
    
    if status == "Draft": btns = [dbc.Button("Save Draft", id={"type": "action-btn", "index": "save"}, color="secondary", outline=True, **btn_props), dbc.Button("Send to Customer", id={"type": "action-btn", "index": "send"}, color="primary", **btn_props)]
    elif status == "Sent": btns = [dbc.Button("Mark Approved", id={"type": "action-btn", "index": "approve"}, color="success", **btn_props)]
    elif status == "Approved": btns = [dbc.Button("Ready to Schedule", disabled=True, color="warning", **btn_props), html.Small("Go to Schedule Tab to Dispatch", className="text-muted d-block text-center")]
    elif status == "Scheduled": btns = [dbc.Button("⚠ Update Active Job", id={"type": "action-btn", "index": "save"}, color="danger", outline=True, **btn_props), dbc.Button("Complete & Invoice", id={"type": "action-btn", "index": "complete"}, color="success", **btn_props)]
    else: btns = [dbc.Button("Job Closed", disabled=True, color="secondary", **btn_props)]
    btns.append(dl_btn)

    return (state, cart, f"${total:,.2f}", f"Margin: ${margin:,.2f}", JobStepper(status), btns, toast, pdf_download, state['tax'], c_name_res, c_price_res)

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
