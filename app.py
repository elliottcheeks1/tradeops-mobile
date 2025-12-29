import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.express as px
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
DB_FILE = "tradeops.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Customers Table
    c.execute('''CREATE TABLE IF NOT EXISTS customers 
                 (id TEXT PRIMARY KEY, name TEXT, address TEXT, email TEXT)''')
    
    # Catalog Table
    c.execute('''CREATE TABLE IF NOT EXISTS catalog 
                 (id TEXT PRIMARY KEY, name TEXT, type TEXT, cost REAL, price REAL)''')
    
    # Quotes Table (Stores complex items as JSON for this POC)
    c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                 (id TEXT PRIMARY KEY, customer_id TEXT, status TEXT, 
                  created_at TEXT, scheduled_date TEXT, tech TEXT, 
                  items_json TEXT, tax REAL, discount REAL, fee REAL, 
                  notes TEXT, total REAL)''')
    
    # Seed Data (Only if empty)
    c.execute("SELECT count(*) FROM customers")
    if c.fetchone()[0] == 0:
        customers = [
            ("C-1", "Burger King #402", "123 Whopper Ln", "bk@franchise.com"),
            ("C-2", "Marriott Downtown", "400 Congress Ave", "mgr@marriott.com"),
        ]
        c.executemany("INSERT INTO customers VALUES (?,?,?,?)", customers)
        
        catalog = [
            ("P-1", "16 SEER Condenser", "Part", 1200.0, 2800.0),
            ("P-2", "Evaporator Coil", "Part", 450.0, 950.0),
            ("L-1", "Master Labor", "Labor", 60.0, 185.0),
            ("L-2", "Apprentice Labor", "Labor", 25.0, 85.0),
        ]
        c.executemany("INSERT INTO catalog VALUES (?,?,?,?,?)", catalog)
        
    conn.commit()
    conn.close()

# Run DB Init
init_db()

# DB Helper Functions
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
    "bg_main": "#F4F7F6", "bg_card": "#FFFFFF", "text": "#2c3e50"
}

custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; }}
    .sidebar {{ position: fixed; top: 0; left: 0; bottom: 0; width: 250px; padding: 2rem 1rem; background: #fff; border-right: 1px solid #eee; z-index: 1000; }}
    .content {{ margin-left: 260px; padding: 2rem; }}
    .saas-card {{ background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #f0f0f0; }}
    .stepper-item {{ text-align: center; position: relative; z-index: 1; }}
    .stepper-item.active .step-circle {{ background-color: {THEME['primary']}; color: white; border: none; }}
    .stepper-item.completed .step-circle {{ background-color: {THEME['success']}; color: white; border: none; }}
    .step-circle {{ width: 30px; height: 30px; border-radius: 50%; background: #eee; display: flex; align-items: center; justify-content: center; margin: 0 auto 5px auto; font-weight: bold; font-size: 12px; color: #777; }}
    .nav-link {{ color: #555; font-weight: 500; padding: 10px 15px; border-radius: 8px; transition: 0.2s; }}
    .nav-link:hover, .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; }}
    .table-hover tbody tr:hover {{ background-color: #f8f9fa; cursor: pointer; }}
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
#   3. COMPONENTS
# =========================================================
def Sidebar():
    return html.Div([
        html.H3("TradeOps", className="fw-bold mb-5", style={"color": THEME['primary']}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-2"), "Pipeline"], href="/pipeline", active="exact"),
            dbc.NavLink([html.I(className="bi bi-plus-circle me-2"), "New Quote"], href="/builder/new", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-week me-2"), "Schedule"], href="/schedule", active="exact"),
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
#   4. VIEWS
# =========================================================

def DashboardView():
    df_quotes = get_df("SELECT * FROM quotes")
    total_rev = df_quotes['total'].sum()
    df_quotes['created_at'] = pd.to_datetime(df_quotes['created_at'])
    monthly_rev = df_quotes[df_quotes['created_at'] >= (datetime.now() - timedelta(days=30))]['total'].sum()
    
    # Win Rate Calculation
    closed = df_quotes[df_quotes['status'].isin(['Paid', 'Invoiced', 'Lost'])]
    won = df_quotes[df_quotes['status'].isin(['Paid', 'Invoiced'])]
    win_rate = (len(won) / len(closed) * 100) if len(closed) > 0 else 0

    return html.Div([
        html.H2("Business Insights", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue MTD"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Open Estimates"), html.H3(len(df_quotes[df_quotes['status'].isin(['Draft','Sent'])]), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Win Rate"), html.H3(f"{win_rate:.0f}%", className="fw-bold text-success")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Revenue Goal ($50k)"), dbc.Progress(value=(monthly_rev/50000)*100, color="primary", className="mt-2")], className="saas-card"), md=3),
        ])
    ])

def PipelineView():
    df = get_df("""
        SELECT q.id, c.name as customer, q.status, q.total, q.created_at, q.tech 
        FROM quotes q JOIN customers c ON q.customer_id = c.id 
        ORDER BY q.created_at DESC
    """)
    
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("Quote Pipeline", className="fw-bold"), width=9),
            dbc.Col(dbc.Button("+ New Quote", href="/builder/new", color="primary", className="float-end"), width=3)
        ], className="mb-4"),
        
        html.Div([
            dash_table.DataTable(
                id='pipeline-table',
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Customer", "id": "customer"},
                    {"name": "Status", "id": "status"},
                    {"name": "Tech", "id": "tech"},
                    {"name": "Date", "id": "created_at"},
                    {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}},
                ],
                data=df.to_dict('records'),
                style_as_list_view=True,
                style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                style_cell={'padding': '12px', 'textAlign': 'left'},
                row_selectable='single'
            )
        ], className="saas-card")
    ])

def QuoteBuilderView(quote_id=None):
    # Default State
    state = {
        "id": "Q-NEW", "status": "Draft", "customer_id": None, "items": [], 
        "tax": 0, "discount": 0, "fee": 0, "notes": "", "tech": "Unassigned"
    }
    
    # Load Existing Quote
    if quote_id and quote_id != "new":
        df = get_df("SELECT * FROM quotes WHERE id = ?", (quote_id,))
        if not df.empty:
            row = df.iloc[0]
            state = {
                "id": row['id'], "status": row['status'], "customer_id": row['customer_id'],
                "items": json.loads(row['items_json']), "tax": row['tax'], 
                "discount": row['discount'], "fee": row['fee'], "notes": row['notes'], "tech": row['tech']
            }

    customers = get_df("SELECT id, name FROM customers")
    catalog = get_df("SELECT * FROM catalog")

    return html.Div([
        dcc.Store(id="quote-state", data=state),
        dcc.Download(id="download-pdf"),
        
        # Scheduling Modal
        dbc.Modal([
            dbc.ModalHeader("Schedule Job"),
            dbc.ModalBody([
                dbc.Label("Assign Technician"),
                dbc.Select(id="sched-tech", options=[{"label": t, "value": t} for t in ["Elliott", "Sarah", "Mike", "John"]]),
                html.Br(),
                dbc.Label("Select Date"),
                dcc.DatePickerSingle(id="sched-date", date=date.today(), display_format="YYYY-MM-DD")
            ]),
            dbc.ModalFooter(dbc.Button("Confirm Schedule", id="btn-confirm-schedule", color="primary"))
        ], id="modal-schedule", is_open=False),

        # Header
        dbc.Row([
            dbc.Col(html.H2(f"Quote: {state['id']}", className="fw-bold"), width=8),
            dbc.Col(html.Div(id="stepper-container"), width=12)
        ]),

        dbc.Row([
            # LEFT: Customer & Actions
            dbc.Col([
                html.Div([
                    html.H5("Customer & Info", className="fw-bold mb-3"),
                    dcc.Dropdown(
                        id="cust-select", 
                        options=[{'label': r['name'], 'value': r['id']} for _, r in customers.iterrows()], 
                        value=state['customer_id'],
                        placeholder="Select Customer..."
                    ),
                    html.Br(),
                    dbc.Label("Internal Notes"),
                    dbc.Textarea(id="quote-notes", value=state['notes'], placeholder="Gate code, dogs, etc...", style={"height": "100px"}),
                    html.Hr(),
                    html.H5("Actions", className="fw-bold mb-3"),
                    html.Div(id="action-buttons"),
                    html.Div(id="toast-container")
                ], className="saas-card h-100")
            ], md=4),

            # RIGHT: Line Items
            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold mb-3"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="catalog-select", options=[{'label': f"{r['name']} (${r['price']})", 'value': r['id']} for _, r in catalog.iterrows()], placeholder="Add Item..."), md=7),
                        dbc.Col(dbc.Input(id="item-qty", type="number", value=1, min=1), md=2),
                        dbc.Col(dbc.Button("Add", id="btn-add-item", color="primary", className="w-100"), md=3)
                    ], className="mb-3"),

                    # Cart List
                    html.Div(id="cart-container", className="mb-4"),

                    html.Hr(),
                    
                    # Financials
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
    df = get_df("SELECT * FROM quotes WHERE status = 'Scheduled'")
    if df.empty:
        df = pd.DataFrame(columns=['scheduled_date', 'tech', 'customer_id', 'id'])
    
    return html.Div([
        html.H2("Dispatch Board", className="fw-bold mb-4"),
        html.Div([
            dcc.Graph(
                figure=px.timeline(
                    df, x_start="scheduled_date", x_end="scheduled_date", y="tech", color="tech", 
                    text="id", title="Technician Schedule"
                ).update_layout(template="plotly_white", height=600).update_yaxes(categoryorder="total ascending")
            ) if not df.empty else html.P("No scheduled jobs found.")
        ], className="saas-card")
    ])

# =========================================================
#   5. MAIN LAYOUT & CALLBACKS
# =========================================================
app.layout = html.Div([dcc.Location(id="url"), Sidebar(), html.Div(id="page-content", className="content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def router(path):
    if path == "/pipeline": return PipelineView()
    if path.startswith("/builder/"): return QuoteBuilderView(path.split("/")[-1])
    if path == "/schedule": return ScheduleView()
    return DashboardView()

@app.callback(Output("url", "pathname"), Input("pipeline-table", "selected_rows"), State("pipeline-table", "data"))
def go_to_quote(selected, data):
    if selected: return f"/builder/{data[selected[0]]['id']}"
    return dash.no_update

# --- Main Quote Logic (Add, Delete, Save, Transition) ---
@app.callback(
    [Output("quote-state", "data"), 
     Output("cart-container", "children"), 
     Output("total-display", "children"), 
     Output("margin-display", "children"),
     Output("stepper-container", "children"), 
     Output("action-buttons", "children"), 
     Output("modal-schedule", "is_open"),
     Output("toast-container", "children")],
    [Input("btn-add-item", "n_clicks"),
     Input({"type": "btn-delete", "index": ALL}, "n_clicks"),
     Input({"type": "action-btn", "index": ALL}, "n_clicks"),
     Input("in-tax", "value"), Input("in-discount", "value"), Input("in-fee", "value"),
     Input("btn-confirm-schedule", "n_clicks"),
     Input("quote-notes", "value"), Input("cust-select", "value")],
    [State("catalog-select", "value"), State("item-qty", "value"), 
     State("quote-state", "data"), State("sched-tech", "value"), State("sched-date", "date")]
)
def update_quote_logic(n_add, n_del, n_action, tax, disc, fee, n_sched, notes, cust_id, 
                       cat_id, qty, state, sched_tech, sched_date):
    
    ctx_id = ctx.triggered_id
    toast = None
    
    # 1. Update Basic Inputs
    state['tax'] = tax or 0
    state['discount'] = disc or 0
    state['fee'] = fee or 0
    state['notes'] = notes or ""
    state['customer_id'] = cust_id

    # 2. Add Item
    if ctx_id == "btn-add-item" and cat_id:
        catalog = get_df("SELECT * FROM catalog WHERE id = ?", (cat_id,)).iloc[0]
        state['items'].append({
            "uuid": str(uuid.uuid4()), "id": catalog['id'], "name": catalog['name'], 
            "qty": float(qty or 1), "price": catalog['price'], "cost": catalog['cost']
        })

    # 3. Delete Item
    if isinstance(ctx_id, dict) and ctx_id['type'] == "btn-delete":
        item_uuid = ctx_id['index']
        state['items'] = [i for i in state['items'] if i['uuid'] != item_uuid]

    # 4. Financial Calcs
    subtotal = sum(i['qty'] * i['price'] for i in state['items'])
    total_cost = sum(i['qty'] * i['cost'] for i in state['items'])
    total = subtotal + state['fee'] + state['tax'] - state['discount']
    margin = total - total_cost
    margin_pct = (margin / total * 100) if total > 0 else 0
    state['total'] = total

    # 5. Workflow Transitions & Saving
    sched_modal_open = False
    
    # Helper to save to DB
    def save_to_db():
        if state['id'] == "Q-NEW":
            new_id = f"Q-{random.randint(10000,99999)}"
            state['id'] = new_id
            created = date.today().strftime("%Y-%m-%d")
            execute_query("INSERT INTO quotes (id, customer_id, status, created_at, items_json, tax, discount, fee, notes, total, tech) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (new_id, state['customer_id'], state['status'], created, json.dumps(state['items']), state['tax'], state['discount'], state['fee'], state['notes'], state['total'], state['tech']))
        else:
            execute_query("UPDATE quotes SET status=?, items_json=?, tax=?, discount=?, fee=?, notes=?, total=?, tech=?, scheduled_date=? WHERE id=?",
                          (state['status'], json.dumps(state['items']), state['tax'], state['discount'], state['fee'], state['notes'], state['total'], state.get('tech'), state.get('scheduled_date'), state['id']))

    if isinstance(ctx_id, dict) and ctx_id['type'] == "action-btn":
        action = ctx_id['index']
        if action == "save":
            save_to_db()
            toast = dbc.Toast("Quote Saved!", header="Success", duration=3000, icon="success", style={"position": "fixed", "top": 10, "right": 10})
        elif action == "send":
            state['status'] = "Sent"
            save_to_db()
            toast = dbc.Toast("Email sent to customer (Mock)", header="Email Sent", duration=3000, icon="primary", style={"position": "fixed", "top": 10, "right": 10})
        elif action == "approve":
            state['status'] = "Approved"
            save_to_db()
        elif action == "schedule_prompt":
            sched_modal_open = True # Open Modal
        elif action == "complete":
            state['status'] = "Paid"
            save_to_db()

    # 6. Handle Schedule Confirm
    if ctx_id == "btn-confirm-schedule":
        state['status'] = "Scheduled"
        state['tech'] = sched_tech
        state['scheduled_date'] = sched_date
        save_to_db()
        sched_modal_open = False
        toast = dbc.Toast(f"Job assigned to {sched_tech}", header="Scheduled", duration=3000, icon="success", style={"position": "fixed", "top": 10, "right": 10})

    # 7. Render UI
    
    # Cart HTML with Delete Buttons
    cart_rows = []
    for item in state['items']:
        cart_rows.append(dbc.Row([
            dbc.Col(item['name'], width=5),
            dbc.Col(f"x{item['qty']}", width=2),
            dbc.Col(f"${item['price']*item['qty']:.2f}", width=3),
            dbc.Col(dbc.Button("❌", id={"type": "btn-delete", "index": item['uuid']}, size="sm", color="link", className="text-danger p-0"), width=2, className="text-end"),
        ], className="border-bottom py-2 align-items-center"))

    # Dynamic Buttons
    status = state['status']
    btn_style = {"width": "100%", "marginBottom": "5px"}
    
    if status == "Draft":
        btns = [
            dbc.Button("Save Draft", id={"type": "action-btn", "index": "save"}, color="secondary", outline=True, style=btn_style),
            dbc.Button("Send to Customer", id={"type": "action-btn", "index": "send"}, color="primary", style=btn_style)
        ]
    elif status == "Sent":
        btns = [
            dbc.Button("Mark Approved", id={"type": "action-btn", "index": "approve"}, color="success", style=btn_style),
            dbc.Button("Resend Email", id={"type": "action-btn", "index": "send"}, color="info", outline=True, style=btn_style)
        ]
    elif status == "Approved":
        btns = [dbc.Button("Schedule Job", id={"type": "action-btn", "index": "schedule_prompt"}, color="warning", style=btn_style)]
    elif status == "Scheduled":
        btns = [
            dbc.Button("Complete & Invoice", id={"type": "action-btn", "index": "complete"}, color="success", style=btn_style),
            html.Small(f"Scheduled: {state.get('tech')} on {state.get('scheduled_date')}", className="text-muted d-block text-center")
        ]
    else:
        btns = [dbc.Button("Closed / Paid", disabled=True, color="secondary", style=btn_style)]

    margin_display = f"Margin: ${margin:.2f} ({margin_pct:.1f}%)"

    return (state, cart_rows, f"${total:,.2f}", margin_display, 
            JobStepper(status), btns, sched_modal_open, toast)

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
