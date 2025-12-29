import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import random
import uuid

# =========================================================
#   1. MOCK DATABASE (Simulates Backend)
# =========================================================
class MockDB:
    def __init__(self):
        # Initial Seed Data
        self.customers = [
            {"id": "C-1", "name": "Burger King #402", "address": "123 Whopper Ln", "city": "Austin", "email": "bk402@franchise.com"},
            {"id": "C-2", "name": "Marriott Downtown", "address": "400 Congress Ave", "city": "Austin", "email": "manager@marriott.com"},
            {"id": "C-3", "name": "Residential - John Doe", "address": "88 Maple St", "city": "Round Rock", "email": "john@gmail.com"},
        ]
        
        self.catalog = [
            {"id": "P-1", "name": "16 SEER Condenser (3 Ton)", "type": "Part", "cost": 1200, "price": 2800},
            {"id": "P-2", "name": "Evaporator Coil", "type": "Part", "cost": 450, "price": 950},
            {"id": "P-3", "name": "Smart Thermostat", "type": "Part", "cost": 120, "price": 350},
            {"id": "L-1", "name": "Labor - Master Tech", "type": "Labor", "cost": 60, "price": 185},
            {"id": "L-2", "name": "Labor - Apprentice", "type": "Labor", "cost": 25, "price": 85},
            {"id": "L-3", "name": "Trip Charge", "type": "Labor", "cost": 10, "price": 79},
        ]
        
        self.quotes = []
        self._seed_quotes()

    def _seed_quotes(self):
        statuses = ["Draft", "Sent", "Approved", "Scheduled", "Invoiced", "Paid"]
        techs = ["Elliott", "Sarah", "Mike"]
        
        for i in range(1001, 1030):
            q_id = f"Q-{i}"
            cust = random.choice(self.customers)
            status = random.choice(statuses)
            # Random items
            items = []
            for _ in range(random.randint(1, 4)):
                item = random.choice(self.catalog)
                qty = random.randint(1, 3)
                items.append({
                    "id": str(uuid.uuid4()), "catalog_id": item['id'], "desc": item['name'], 
                    "type": item['type'], "qty": qty, "price": item['price'], "cost": item['cost']
                })
            
            total = sum(x['qty'] * x['price'] for x in items)
            
            self.quotes.append({
                "id": q_id,
                "customer_id": cust['id'],
                "customer_name": cust['name'],
                "address": cust['address'],
                "status": status,
                "created_at": (date.today() - timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d"),
                "tech": random.choice(techs),
                "items": items,
                "total": total
            })

    # CRUD Operations
    def get_quotes(self): return pd.DataFrame(self.quotes)
    def get_customers(self): return self.customers
    def get_catalog(self): return self.catalog
    
    def add_customer(self, name, address, city, email):
        new_id = f"C-{len(self.customers) + 1}"
        self.customers.append({"id": new_id, "name": name, "address": address, "city": city, "email": email})
        return new_id
        
    def add_catalog_item(self, name, type, cost, price):
        new_id = f"{type[0]}-{len(self.catalog) + 1}"
        self.catalog.append({"id": new_id, "name": name, "type": type, "cost": float(cost), "price": float(price)})
        
    def update_quote_status(self, quote_id, status):
        for q in self.quotes:
            if q['id'] == quote_id:
                q['status'] = status
                return True
        return False
        
    def save_quote(self, quote_data):
        # Update existing or Create new
        idx = next((i for i, q in enumerate(self.quotes) if q['id'] == quote_data['id']), None)
        if idx is not None:
            self.quotes[idx] = quote_data
        else:
            self.quotes.append(quote_data)

# Initialize Singleton DB
db = MockDB()

# =========================================================
#   2. THEME & CSS
# =========================================================
THEME = {
    "primary": "#2665EB",    "secondary": "#6c757d",
    "success": "#28a745",    "bg_main": "#F4F7F6",
    "bg_card": "#FFFFFF",    "text": "#2c3e50"
}

custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; }}
    .sidebar {{
        position: fixed; top: 0; left: 0; bottom: 0; width: 250px;
        padding: 2rem 1rem; background-color: #ffffff;
        box-shadow: 2px 0 10px rgba(0,0,0,0.05); z-index: 1000;
    }}
    .content {{ margin-left: 260px; padding: 2rem; }}
    .saas-card {{
        background-color: #ffffff; border-radius: 12px; border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 1.5rem; margin-bottom: 1.5rem;
    }}
    .stepper-item {{ text-align: center; position: relative; z-index: 1; }}
    .stepper-item.active .step-circle {{ background-color: {THEME['primary']}; color: white; border: none; }}
    .stepper-item.completed .step-circle {{ background-color: {THEME['success']}; color: white; border: none; }}
    .step-circle {{
        width: 30px; height: 30px; border-radius: 50%; border: 2px solid #ddd;
        background: #fff; display: flex; align-items: center; justify-content: center;
        margin: 0 auto 5px auto; font-weight: bold; font-size: 12px; color: #999;
    }}
    .nav-link {{ color: #555; font-weight: 500; padding: 10px 15px; border-radius: 8px; transition: 0.2s; }}
    .nav-link:hover, .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; }}
"""

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
server = app.server

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%} <title>{%title%}</title> {%favicon%} {%css%}
        <style>''' + custom_css + '''</style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%} {%scripts%} {%renderer%}</footer>
    </body>
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
    pdf.cell(0, 10, f"Customer: {quote_data.get('customer_name', 'Valued Client')}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 10, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Price", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", "", 10)
    for item in quote_data.get('items', []):
        pdf.cell(100, 10, item['desc'], 1)
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
        html.H3("TradeOps", className="fw-bold mb-5", style={"color": THEME['primary']}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-week me-2"), "Schedule"], href="/schedule", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-2"), "Quotes"], href="/quotes", active="exact"),
            dbc.NavLink([html.I(className="bi bi-gear me-2"), "Settings"], href="/settings", active="exact"),
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
    df = db.get_quotes()
    total_rev = df['total'].sum()
    monthly_rev = df[df['created_at'] >= (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")]['total'].sum()
    
    fig = px.line(df.groupby('created_at')['total'].sum().reset_index(), x='created_at', y='total', markers=True)
    fig.update_layout(template="plotly_white", margin=dict(l=20,r=20,t=20,b=20), height=300)
    
    return html.Div([
        html.H2("Business Insights", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col(html.Div([html.H6("Revenue MTD"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Open Estimates"), html.H3(len(df[df['status'].isin(['Draft','Sent'])]), className="fw-bold")], className="saas-card"), md=3),
            dbc.Col(html.Div([html.H6("Avg Job Size"), html.H3(f"${df['total'].mean():,.0f}", className="fw-bold")], className="saas-card"), md=3),
        ], className="mb-4"),
        html.Div([html.H5("Revenue Trend", className="fw-bold"), dcc.Graph(figure=fig)], className="saas-card")
    ])

def QuoteBuilderView():
    return html.Div([
        dcc.Store(id="quote-state", data={"id": "Q-NEW", "status": "Draft", "items": [], "total": 0, "customer_name": ""}),
        dcc.Download(id="download-pdf"),
        
        # New Customer Modal
        dbc.Modal([
            dbc.ModalHeader("Create New Customer"),
            dbc.ModalBody([
                dbc.Input(id="new-cust-name", placeholder="Name / Company", className="mb-2"),
                dbc.Input(id="new-cust-addr", placeholder="Street Address", className="mb-2"),
                dbc.Input(id="new-cust-city", placeholder="City", className="mb-2"),
                dbc.Input(id="new-cust-email", placeholder="Email", className="mb-2"),
            ]),
            dbc.ModalFooter(dbc.Button("Create Customer", id="btn-create-cust", color="success"))
        ], id="modal-cust", is_open=False),

        dbc.Row([dbc.Col(html.H2("Quote Builder", className="fw-bold"), width=8), dbc.Col(html.Div(id="stepper-container"), width=12)]),
        
        dbc.Row([
            # LEFT: Customer
            dbc.Col([
                html.Div([
                    html.H5("Customer", className="fw-bold mb-3"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="cust-select", options=[{'label': c['name'], 'value': c['id']} for c in db.get_customers()], placeholder="Select Customer..."), width=8),
                        dbc.Col(dbc.Button(html.I(className="bi bi-person-plus"), id="btn-open-cust-modal", color="light"), width=4)
                    ], className="mb-3"),
                    
                    dbc.Label("Service Address"),
                    dbc.Input(id="job-address", placeholder="123 Main St", className="mb-3"),
                    
                    html.Hr(),
                    html.H5("Actions", className="fw-bold mb-3"),
                    html.Div(id="action-buttons")
                ], className="saas-card h-100")
            ], md=4),
            
            # RIGHT: Items
            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold mb-3"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="catalog-select", options=[{'label': f"{i['name']} (${i['price']})", 'value': i['id']} for i in db.get_catalog()], placeholder="Search Parts/Labor..."), md=7),
                        dbc.Col(dbc.Input(id="item-qty", type="number", value=1, min=1), md=2),
                        dbc.Col(dbc.Button("Add", id="btn-add-item", color="primary", className="w-100"), md=3)
                    ], className="mb-3"),
                    
                    html.Div(id="cart-container", style={"minHeight": "200px"}),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col(html.H4("Total", className="text-muted"), width=6),
                        dbc.Col(html.H2(id="total-display", className="fw-bold text-end text-success"), width=6),
                    ])
                ], className="saas-card h-100")
            ], md=8),
        ])
    ])

def SettingsView():
    return html.Div([
        html.H2("Settings & Catalog", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Add Catalog Item", className="fw-bold mb-3"),
                    dbc.Input(id="cat-name", placeholder="Item Name", className="mb-2"),
                    dbc.Select(id="cat-type", options=[{"label": "Part", "value": "Part"}, {"label": "Labor", "value": "Labor"}], value="Part", className="mb-2"),
                    dbc.Row([
                        dbc.Col(dbc.Input(id="cat-cost", type="number", placeholder="Cost"), width=6),
                        dbc.Col(dbc.Input(id="cat-price", type="number", placeholder="Price"), width=6),
                    ], className="mb-3"),
                    dbc.Button("Add to Catalog", id="btn-add-catalog", color="primary", className="w-100"),
                    html.Div(id="cat-msg", className="mt-2 text-success")
                ], className="saas-card")
            ], md=4),
            dbc.Col([
                html.Div([
                    html.H5("Current Catalog", className="fw-bold mb-3"),
                    dash_table.DataTable(
                        id="catalog-table",
                        data=db.get_catalog(),
                        columns=[{"name": "Name", "id": "name"}, {"name": "Type", "id": "type"}, {"name": "Price", "id": "price", "format": {"specifier": "$,.2f"}}],
                        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
                        style_cell={'textAlign': 'left', 'padding': '10px'}
                    )
                ], className="saas-card")
            ], md=8)
        ])
    ])

def ScheduleView():
    df = db.get_quotes()
    df_sched = df[df['status'] == 'Scheduled']
    return html.Div([
        html.H2("Smart Schedule", className="fw-bold mb-4"),
        html.Div([
            dcc.Graph(figure=px.timeline(df_sched, x_start="created_at", x_end="created_at", y="tech", color="tech", title="Dispatch View").update_layout(template="plotly_white"))
        ], className="saas-card")
    ])

# =========================================================
#   6. MAIN LAYOUT & CALLBACKS
# =========================================================
app.layout = html.Div([dcc.Location(id="url"), Sidebar(), html.Div(id="page-content", className="content")])

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(path):
    if path == "/quotes": return QuoteBuilderView()
    if path == "/schedule": return ScheduleView()
    if path == "/settings": return SettingsView()
    return DashboardView()

# --- Customer & Address Logic ---
@app.callback(
    [Output("modal-cust", "is_open"), Output("cust-select", "options"), Output("cust-select", "value")],
    [Input("btn-open-cust-modal", "n_clicks"), Input("btn-create-cust", "n_clicks")],
    [State("modal-cust", "is_open"), State("new-cust-name", "value"), State("new-cust-addr", "value"), State("new-cust-city", "value"), State("new-cust-email", "value")]
)
def manage_customer(n_open, n_create, is_open, name, addr, city, email):
    ctx_id = ctx.triggered_id
    if ctx_id == "btn-open-cust-modal": return True, dash.no_update, dash.no_update
    if ctx_id == "btn-create-cust" and name:
        new_id = db.add_customer(name, addr, city, email)
        return False, [{'label': c['name'], 'value': c['id']} for c in db.get_customers()], new_id
    return is_open, [{'label': c['name'], 'value': c['id']} for c in db.get_customers()], dash.no_update

@app.callback(Output("job-address", "value"), Input("cust-select", "value"))
def fill_address(cust_id):
    if not cust_id: return ""
    cust = next((c for c in db.get_customers() if c['id'] == cust_id), None)
    return cust['address'] if cust else ""

# --- Catalog Settings Logic ---
@app.callback(
    [Output("catalog-table", "data"), Output("cat-msg", "children"), Output("catalog-select", "options")],
    Input("btn-add-catalog", "n_clicks"),
    [State("cat-name", "value"), State("cat-type", "value"), State("cat-cost", "value"), State("cat-price", "value")]
)
def add_catalog_item(n, name, type, cost, price):
    if n and name and price:
        db.add_catalog_item(name, type, cost, price)
        cat = db.get_catalog()
        return cat, "Item added!", [{'label': f"{i['name']} (${i['price']})", 'value': i['id']} for i in cat]
    cat = db.get_catalog()
    return cat, "", [{'label': f"{i['name']} (${i['price']})", 'value': i['id']} for i in cat]

# --- Quote Builder Logic (Items, State, PDF) ---
@app.callback(
    [Output("quote-state", "data"), Output("cart-container", "children"), Output("total-display", "children"),
     Output("stepper-container", "children"), Output("action-buttons", "children"), Output("download-pdf", "data")],
    [Input("btn-add-item", "n_clicks"), Input({"type": "action-btn", "index": dash.ALL}, "n_clicks")],
    [State("catalog-select", "value"), State("item-qty", "value"), State("quote-state", "data"), State("cust-select", "value"), State("job-address", "value")]
)
def update_quote(n_add, n_action, cat_id, qty, state, cust_id, addr):
    ctx_id = ctx.triggered_id
    
    # Update Customer Info in State
    if cust_id:
        c = next((x for x in db.get_customers() if x['id'] == cust_id), None)
        state['customer_name'] = c['name'] if c else "Unknown"
    
    # Add Item
    if ctx_id == "btn-add-item" and cat_id:
        item = next((i for i in db.get_catalog() if i['id'] == cat_id), None)
        if item:
            state['items'].append({"desc": item['name'], "qty": float(qty), "price": item['price']})

    # Lifecycle State
    pdf_file = None
    if isinstance(ctx_id, dict):
        action = ctx_id['index']
        if action == "send":
            state['status'] = "Sent"
            pdf_file = dcc.send_bytes(create_pdf(state), f"Quote_{state['id']}.pdf")
        elif action == "approve": state['status'] = "Approved"
        elif action == "schedule": state['status'] = "Scheduled"
        elif action == "complete": state['status'] = "Paid"
        db.save_quote(state) # Persist to mock DB

    # Recalculate
    total = sum(x['qty']*x['price'] for x in state['items'])
    state['total'] = total
    
    # Render Cart
    cart = [dbc.Row([dbc.Col(i['desc'], width=6), dbc.Col(f"x{i['qty']}", width=2), dbc.Col(f"${i['price']*i['qty']:.2f}", width=4)], className="border-bottom py-2") for i in state['items']]
    
    # Buttons
    status = state['status']
    btn_props = {"style": {"width": "100%", "marginBottom": "10px"}}
    if status == "Draft": btns = [dbc.Button("Send (PDF)", id={"type": "action-btn", "index": "send"}, color="primary", **btn_props)]
    elif status == "Sent": btns = [dbc.Button("Approve", id={"type": "action-btn", "index": "approve"}, color="success", **btn_props)]
    elif status == "Approved": btns = [dbc.Button("Schedule", id={"type": "action-btn", "index": "schedule"}, color="warning", **btn_props)]
    elif status == "Scheduled": btns = [dbc.Button("Complete", id={"type": "action-btn", "index": "complete"}, color="success", **btn_props)]
    else: btns = [dbc.Button("Closed", disabled=True, color="secondary", **btn_props)]

    return state, cart, f"${total:,.2f}", JobStepper(status), btns, pdf_file

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
