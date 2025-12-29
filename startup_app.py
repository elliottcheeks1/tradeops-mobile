import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import re
import io

# =========================================================
#   MOCK DATA LAYER (IN-MEMORY ONLY)
# =========================================================

# Customers
MOCK_CUSTOMERS = [
    {"customer_id": "CUST-1001", "name": "Brenda Caulfield", "street": "123 Maple St", "city": "Houston", "state": "TX", "zip": "77001", "phone": "555-0101"},
    {"customer_id": "CUST-1002", "name": "Kevin Parker", "street": "421 Pine Dr", "city": "Katy", "state": "TX", "zip": "77450", "phone": "555-0102"},
    {"customer_id": "CUST-1003", "name": "High Point Creamery", "street": "88 Dairy Ln", "city": "Cypress", "state": "TX", "zip": "77429", "phone": "555-0103"},
    {"customer_id": "CUST-1004", "name": "Johnathan Riley", "street": "600 Oak Blvd", "city": "Spring", "state": "TX", "zip": "77373", "phone": "555-0104"},
]

# Parts catalog
MOCK_PARTS = [
    {"part_id": "P1", "name": "16 SEER AC Condenser", "cost": 1200.0, "retail_price": 2800.0},
    {"part_id": "P2", "name": "Evaporator Coil", "cost": 450.0, "retail_price": 1150.0},
    {"part_id": "P3", "name": "Smart Thermostat", "cost": 90.0, "retail_price": 325.0},
    {"part_id": "P4", "name": "Panel Upgrade 200A", "cost": 750.0, "retail_price": 1950.0},
    {"part_id": "P5", "name": "Drain Cleaning (per line)", "cost": 30.0, "retail_price": 189.0},
]

# Labor catalog
MOCK_LABOR = [
    {"role": "Apprentice", "base_cost": 20.0, "bill_rate": 75.0},
    {"role": "Journeyman", "base_cost": 35.0, "bill_rate": 115.0},
    {"role": "Master Tech", "base_cost": 55.0, "bill_rate": 155.0},
]

# Quotes
MOCK_QUOTES = [
    {"quote_id": "Q-1001", "customer_id": "CUST-1001", "job_type": "Install", "estimator": "Elliott", "status": "Open", "created_at": "2025-01-03", "total_price": 5650.0, "total_cost": 3400.0},
    {"quote_id": "Q-1002", "customer_id": "CUST-1002", "job_type": "Service", "estimator": "Elliott", "status": "Won", "created_at": "2025-01-05", "total_price": 420.0, "total_cost": 150.0},
]

MOCK_QUOTE_ITEMS = [
    {"quote_id": "Q-1001", "item_name": "16 SEER AC Condenser", "item_type": "Part", "unit_cost": 1200.0, "unit_price": 2800.0, "quantity": 1},
    {"quote_id": "Q-1001", "item_name": "Evaporator Coil", "item_type": "Part", "unit_cost": 450.0, "unit_price": 1150.0, "quantity": 1},
    {"quote_id": "Q-1001", "item_name": "Master Tech Labor", "item_type": "Labor", "unit_cost": 55.0, "unit_price": 155.0, "quantity": 8},
    {"quote_id": "Q-1002", "item_name": "Drain Cleaning (per line)", "item_type": "Part", "unit_cost": 30.0, "unit_price": 189.0, "quantity": 1},
    {"quote_id": "Q-1002", "item_name": "Journeyman Labor", "item_type": "Labor", "unit_cost": 35.0, "unit_price": 115.0, "quantity": 2},
]

# Follow-up queue
MOCK_FOLLOWUPS = [
    {"quote_id": "Q-1001", "name": "Brenda Caulfield", "phone": "555-0101", "total_price": 5650.0, "next_followup_date": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"), "followup_status": "Needs Call", "estimator": "Elliott"}
]

# ---------- Helper functions ----------

def get_customers_df(): return pd.DataFrame(MOCK_CUSTOMERS)
def get_parts_df(): return pd.DataFrame(MOCK_PARTS)
def get_labor_df(): return pd.DataFrame(MOCK_LABOR)
def _quotes_df(): return pd.DataFrame(MOCK_QUOTES)
def _quote_items_df(): return pd.DataFrame(MOCK_QUOTE_ITEMS)
def _followups_df(): return pd.DataFrame(MOCK_FOLLOWUPS)

def get_quote_history(estimator_name=None):
    q = _quotes_df()
    c = get_customers_df()[["customer_id", "name"]]
    df = q.merge(c, on="customer_id", how="left")
    if estimator_name:
        df = df[df["estimator"].str.contains(estimator_name, case=False, na=False)]
    df = df.sort_values("created_at", ascending=False)
    return df

def get_followup_queue():
    return _followups_df().sort_values("next_followup_date")

def get_quote_details(quote_id):
    q = _quotes_df()
    qi = _quote_items_df()
    header = q[q["quote_id"] == quote_id].iloc[0]
    items = qi[qi["quote_id"] == quote_id].copy()
    return header, items

def _new_quote_id():
    existing = [int(q["quote_id"].split("-")[1]) for q in MOCK_QUOTES]
    next_num = max(existing + [1000]) + 1
    return f"Q-{next_num}"

def save_new_quote(cust_id, job_type, estimator, items):
    global MOCK_QUOTES, MOCK_QUOTE_ITEMS, MOCK_FOLLOWUPS
    if not items: return None
    qid = _new_quote_id()
    created = datetime.now().strftime("%Y-%m-%d")
    total_cost = sum(i["cost"] * i["qty"] for i in items)
    total_price = sum(i["price"] * i["qty"] for i in items)

    MOCK_QUOTES.append({
        "quote_id": qid, "customer_id": cust_id, "job_type": job_type, "estimator": estimator,
        "status": "Open", "created_at": created, "total_price": total_price, "total_cost": total_cost
    })

    for i in items:
        MOCK_QUOTE_ITEMS.append({
            "quote_id": qid, "item_name": i["name"], "item_type": i["type"],
            "unit_cost": i["cost"], "unit_price": i["price"], "quantity": i["qty"]
        })

    cust = get_customers_df()
    cname = cust[cust["customer_id"] == cust_id]["name"].values[0]
    MOCK_FOLLOWUPS.append({
        "quote_id": qid, "name": cname, "phone": cust[cust["customer_id"] == cust_id]["phone"].values[0],
        "total_price": total_price, "next_followup_date": (date.today() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "followup_status": "Needs Call", "estimator": estimator
    })
    return qid

def update_existing_quote(quote_id, cust_id, job_type, estimator, items):
    global MOCK_QUOTES, MOCK_QUOTE_ITEMS
    total_cost = sum(i["cost"] * i["qty"] for i in items)
    total_price = sum(i["price"] * i["qty"] for i in items)

    for q in MOCK_QUOTES:
        if q["quote_id"] == quote_id:
            q.update({"customer_id": cust_id, "job_type": job_type, "estimator": estimator, 
                      "total_price": total_price, "total_cost": total_cost})
            break

    MOCK_QUOTE_ITEMS = [qi for qi in MOCK_QUOTE_ITEMS if qi["quote_id"] != quote_id]
    for i in items:
        MOCK_QUOTE_ITEMS.append({
            "quote_id": quote_id, "item_name": i["name"], "item_type": i["type"],
            "unit_cost": i["cost"], "unit_price": i["price"], "quantity": i["qty"]
        })

def log_interaction(quote_id, new_status, next_date):
    global MOCK_FOLLOWUPS, MOCK_QUOTES
    for f in MOCK_FOLLOWUPS:
        if f["quote_id"] == quote_id:
            f["followup_status"] = new_status
            f["next_followup_date"] = next_date
    for q in MOCK_QUOTES:
        if q["quote_id"] == quote_id:
            q["status"] = new_status

# =========================================================
#   DASH APP SETUP
# =========================================================

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
app.title = "TradeOps Field"
server = app.server

# =========================================================
#   PDF ENGINE
# =========================================================

def generate_pdf(quote_id, customer_name, items, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_title("TradeOps Field Quote")
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "TradeOps Services", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, "123 Main St, Texas City, TX  |  (555) 555-0100", ln=True, align="C")
    pdf.ln(4)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, 30, 200, 30)
    pdf.ln(8)

    date_str = datetime.now().strftime("%Y-%m-%d")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Quote #: {quote_id}", ln=True)
    pdf.cell(0, 8, f"Customer: {customer_name}", ln=True)
    pdf.cell(0, 8, f"Date: {date_str}", ln=True)
    pdf.ln(8)

    pdf.set_fill_color(246, 248, 250)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(100, 8, "Description", 1, 0, "L", True)
    pdf.cell(30, 8, "Qty", 1, 0, "C", True)
    pdf.cell(50, 8, "Price", 1, 1, "R", True)

    pdf.set_font("Arial", "", 10)
    for item in items:
        pdf.cell(100, 8, str(item["name"]), 1)
        pdf.cell(30, 8, str(item["qty"]), 1, 0, "C")
        pdf.cell(50, 8, f"${item['price']:.2f}", 1, 1, "R")

    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 8, "Total Estimate:", 0, 0, "R")
    pdf.cell(50, 8, f"${total:,.2f}", 0, 1, "R")

    pdf.ln(12)
    pdf.set_font("Arial", "I", 9)
    pdf.multi_cell(0, 5, "This quote is an estimate only and is valid for 30 days. Final pricing may change based on site conditions.")

    clean_name = re.sub(r"[^a-zA-Z0-9]", "", customer_name) or "Customer"
    filename = f"Quote_{clean_name}_{date_str}.pdf"
    pdf.output(filename)
    return filename

# =========================================================
#   UI COMPONENTS
# =========================================================

def kpi_card(id_value, label, icon_class):
    return dbc.Col(dbc.Card([
        dbc.CardBody([
            html.Div([html.I(className=f"{icon_class} me-2 text-primary"), html.Small(label.upper())], className="text-muted"),
            html.H3(id=id_value, className="mt-2 mb-0 fw-bold")
        ])
    ], className="shadow-sm border-0 h-100"), md=3, xs=6, className="mb-3")

followup_tab = dbc.Container([
    html.H4("📞 Follow-Up Queue", className="mt-3 mb-3"),
    dash_table.DataTable(
        id="fup-table",
        columns=[{"name": "Client", "id": "name"}, {"name": "Phone", "id": "phone"}, {"name": "Status", "id": "followup_status"}, {"name": "Due", "id": "next_followup_date"}],
        row_selectable="single", style_cell={"textAlign": "left", "padding": "8px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f6f8fa"}, page_size=8,
    ),
    dbc.Row([
        dbc.Col(dbc.Button("Log Call / Update", id="btn-open-log", color="primary", className="mt-3 w-100", disabled=True), md=4),
        dbc.Col(dbc.Button("Refresh", id="btn-refresh-fup", color="light", className="mt-3 w-100"), md=2),
    ], className="mt-2"),
    dbc.Modal([
        dbc.ModalHeader("Log Interaction"),
        dbc.ModalBody([
            dbc.Label("Outcome"),
            dbc.Select(id="log-outcome", options=[
                {"label": "Left Voicemail", "value": "Left VM"}, {"label": "Spoke - Not Ready", "value": "Needs Call"},
                {"label": "Spoke - Sold!", "value": "Won"}, {"label": "Lost / Not Interested", "value": "Lost"}
            ], value="Needs Call"),
            html.Br(),
            dbc.Label("Next Follow-Up Date"),
            dcc.DatePickerSingle(id="log-date", date=(date.today() + timedelta(days=2)), display_format="YYYY-MM-DD"),
            html.Br(), html.Br(),
            dbc.Button("Save & Update", id="btn-save-log", color="success", className="w-100")
        ])
    ], id="modal-log", is_open=False, centered=True),
], fluid=True)

history_tab = dbc.Container([
    html.H4("📂 Quote History", className="mt-3"),
    dbc.Row([
        dbc.Col(dbc.Input(id="hist-filter-input", placeholder="Filter by estimator...", type="text"), md=6),
        dbc.Col(dbc.Button("Filter", id="btn-filter-hist", color="secondary", className="w-100"), md=2),
        dbc.Col(dbc.Button("Refresh", id="btn-refresh-hist", color="light", className="w-100"), md=2),
    ], className="mb-3"),
    dash_table.DataTable(
        id="history-table",
        columns=[{"name": "Client", "id": "name"}, {"name": "Estimator", "id": "estimator"}, {"name": "Total", "id": "total_price", "type": "numeric", "format": {"specifier": "$,.2f"}}, {"name": "Status", "id": "status"}, {"name": "Created", "id": "created_at"}],
        style_cell={"textAlign": "left", "padding": "8px"}, style_header={"fontWeight": "bold", "backgroundColor": "#f6f8fa"},
        row_selectable="single", page_size=8,
        style_data_conditional=[
            {"if": {"filter_query": "{status} = 'Won'"}, "backgroundColor": "#e6ffed"},
            {"if": {"filter_query": "{status} = 'Lost'"}, "backgroundColor": "#ffeef0"},
        ],
    ),
    dbc.Row([
        dbc.Col(dbc.Button("📝 Edit Quote", id="btn-load-edit", color="warning", className="w-100", disabled=True), md=4),
        dbc.Col(dbc.Button("📄 Download PDF", id="btn-dl-pdf", color="info", className="w-100", disabled=True), md=4),
    ], className="mt-3"),
    dcc.Download(id="download-pdf-component"),
], fluid=True)

quote_tab = dbc.Container([
    dcc.Store(id="cart-store", data=[]),
    dcc.Store(id="edit-mode-store", data={"mode": "new", "qid": None}),
    html.Br(),
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("1. Customer"),
            dbc.CardBody([
                dcc.Dropdown(id="cust-select", options=[], placeholder="Select client..."),
                html.Br(),
                dbc.Button("New Customer", id="btn-new-cust", size="sm", color="light", className="w-100"),
                dbc.Modal([
                    dbc.ModalHeader("New Customer"),
                    dbc.ModalBody([
                        dbc.Input(id="nc-name", placeholder="Company / Name", className="mb-2"),
                        dbc.Input(id="nc-street", placeholder="Street", className="mb-2"),
                        dbc.Input(id="nc-city", placeholder="City", className="mb-2"),
                        dbc.Input(id="nc-zip", placeholder="Zip", className="mb-2"),
                        dbc.Input(id="nc-phone", placeholder="Phone", className="mb-2"),
                        dbc.Button("Save", id="btn-save-nc", color="success", className="w-100"),
                    ])
                ], id="nc-modal", is_open=False, centered=True),
                html.Hr(),
                dbc.Select(id="job-type", options=[{"label": "Service", "value": "Service"}, {"label": "Install", "value": "Install"}], placeholder="Job type", className="mb-2"),
                dbc.Input(id="estimator", placeholder="Estimator name"),
            ])
        ], className="h-100 shadow-sm border-0"), xs=12, lg=4, className="mb-3"),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("2. Items"),
            dbc.CardBody([
                dbc.Tabs([
                    dbc.Tab(label="Parts", children=[
                        html.Br(), dcc.Dropdown(id="part-select", options=[], placeholder="Search catalog..."),
                        dbc.Input(id="part-qty", type="number", placeholder="Qty", value=1, className="mt-2"),
                        dbc.Button("Add Part", id="btn-add-part", color="secondary", className="w-100 mt-2"),
                    ]),
                    dbc.Tab(label="Labor", children=[
                        html.Br(), dbc.Select(id="labor-select", options=[], placeholder="Select role"),
                        dbc.Input(id="labor-hrs", type="number", placeholder="Hours", className="mt-2"),
                        dbc.Button("Add Labor", id="btn-add-labor", color="secondary", className="w-100 mt-2"),
                    ])
                ])
            ])
        ], className="h-100 shadow-sm border-0"), xs=12, lg=4, className="mb-3"),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("3. Summary"),
            dbc.CardBody([
                html.Div(id="cart-list", style={"maxHeight": "220px", "overflowY": "auto"}),
                html.Hr(),
                html.H4(id="cart-total", children="$0.00", className="text-end text-success"),
                dbc.Button("Finalize & Save", id="btn-finalize", color="success", size="lg", className="w-100 mt-2"),
                html.Div(id="save-msg", className="mt-3 text-center"),
            ])
        ], className="h-100 shadow-sm border-0"), xs=12, lg=4, className="mb-3"),
    ])
], fluid=True)

app.layout = html.Div([
    dbc.Navbar([
        dbc.NavbarBrand([html.I(className="bi bi-lightning-charge-fill me-2"), "TradeOps Field"], className="ms-2 fw-bold"),
        dbc.Nav([dbc.NavItem(dbc.NavLink("Tech Console", active=True))], className="ms-3", navbar=True),
        dbc.NavbarToggler(id="navbar-toggler"),
    ], color="dark", dark=True, className="shadow-sm"),
    dbc.Container([
        html.Br(),
        html.Div([html.H2("Hi, Tech 👋", className="fw-bold"), html.P("Here’s what’s happening with your estimates and follow-ups.", className="text-muted")], className="mb-3"),
        dbc.Row([
            kpi_card("metric-open-quotes", "Open Quotes", "bi bi-clipboard"),
            kpi_card("metric-followups-today", "Follow-ups Today", "bi bi-telephone"),
            kpi_card("metric-avg-quote", "Average Quote", "bi bi-cash-coin"),
            kpi_card("metric-won-this-week", "Won This Week", "bi bi-trophy"),
        ]),
        html.Br(),
        dbc.Tabs([
            dbc.Tab(followup_tab, label="Follow-Up", tab_id="tab-fup"),
            dbc.Tab(history_tab, label="History", tab_id="tab-hist"),
            dbc.Tab(quote_tab, label="Builder", tab_id="tab-quote"),
        ], id="tabs", active_tab="tab-fup", className="mt-2"),
        html.Br(),
    ], fluid=True),
], style={"backgroundColor": "#f4f5f7", "minHeight": "100vh"})

# =========================================================
#   CALLBACKS
# =========================================================

@app.callback(
    [Output("metric-open-quotes", "children"), Output("metric-followups-today", "children"), Output("metric-avg-quote", "children"), Output("metric-won-this-week", "children")],
    [Input("tabs", "active_tab"), Input("btn-refresh-fup", "n_clicks"), Input("btn-filter-hist", "n_clicks"), Input("btn-refresh-hist", "n_clicks")]
)
def update_kpis(tab, *_):
    q, fup = _quotes_df(), _followups_df()
    open_count = int((q["status"] == "Open").sum())
    fup_today = int((fup["next_followup_date"] == date.today().strftime("%Y-%m-%d")).sum())
    avg_quote = q["total_price"].mean() if not q.empty else 0.0
    won_week = int(((q["status"] == "Won") & (q["created_at"] >= (date.today() - timedelta(days=7)).strftime("%Y-%m-%d"))).sum())
    return f"{open_count}", f"{fup_today}", f"${avg_quote:,.0f}", f"{won_week}"

@app.callback(
    [Output("cust-select", "options"), Output("part-select", "options"), Output("labor-select", "options"), Output("history-table", "data")],
    [Input("tabs", "active_tab"), Input("btn-filter-hist", "n_clicks"), Input("btn-refresh-hist", "n_clicks")],
    [State("hist-filter-input", "value")]
)
def load_data(tab, n_filter, n_refresh, filter_name):
    cust, parts, labor = get_customers_df(), get_parts_df(), get_labor_df()
    c_opts = [{"label": r["name"], "value": r["customer_id"]} for _, r in cust.iterrows()]
    p_opts = [{"label": f"{r['name']} (${r['retail_price']:.0f})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in parts.iterrows()]
    l_opts = [{"label": f"{r['role']} (${r['bill_rate']}/hr)", "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}"} for _, r in labor.iterrows()]
    return c_opts, p_opts, l_opts, get_quote_history(estimator_name=filter_name).to_dict("records")

@app.callback(
    [Output("modal-log", "is_open"), Output("fup-table", "data"), Output("btn-open-log", "disabled")],
    [Input("btn-open-log", "n_clicks"), Input("btn-save-log", "n_clicks"), Input("tabs", "active_tab"), Input("btn-refresh-fup", "n_clicks"), Input("fup-table", "selected_rows")],
    [State("modal-log", "is_open"), State("fup-table", "data"), State("log-outcome", "value"), State("log-date", "date")]
)
def handle_followup(n_open, n_save, tab, n_refresh, selected, is_open, table_data, outcome, next_date):
    trigger = ctx.triggered_id
    if trigger in ("tabs", "btn-refresh-fup"): return False, get_followup_queue().to_dict("records"), True
    if trigger == "fup-table": return is_open, dash.no_update, not bool(selected)
    if trigger == "btn-open-log": return True, dash.no_update, not bool(selected)
    if trigger == "btn-save-log" and selected:
        log_interaction(table_data[selected[0]]["quote_id"], outcome, next_date)
        return False, get_followup_queue().to_dict("records"), True
    return is_open, dash.no_update, not bool(selected)

@app.callback(
    [Output("tabs", "active_tab", allow_duplicate=True), Output("cust-select", "value", allow_duplicate=True), Output("job-type", "value"), Output("estimator", "value"),
     Output("cart-store", "data", allow_duplicate=True), Output("edit-mode-store", "data"), Output("download-pdf-component", "data"), Output("btn-load-edit", "disabled"), Output("btn-dl-pdf", "disabled")],
    [Input("btn-load-edit", "n_clicks"), Input("btn-dl-pdf", "n_clicks"), Input("history-table", "selected_rows")],
    [State("history-table", "data")], prevent_initial_call=True
)
def handle_history_actions(btn_edit, btn_pdf, selected, data):
    trigger = ctx.triggered_id
    if trigger == "history-table": return (dash.no_update,)*7 + (not bool(selected), not bool(selected))
    if not selected: return (dash.no_update,)*7 + (True, True)
    row = data[selected[0]]
    if trigger == "btn-load-edit":
        h, items = get_quote_details(row["quote_id"])
        cart = items[["item_name", "item_type", "unit_cost", "unit_price", "quantity"]].rename(columns={"item_name":"name", "item_type":"type", "unit_cost":"cost", "unit_price":"price", "quantity":"qty"}).to_dict("records")
        return "tab-quote", h["customer_id"], h["job_type"], h["estimator"], cart, {"mode": "edit", "qid": row["quote_id"]}, dash.no_update, True, True
    if trigger == "btn-dl-pdf":
        h, items = get_quote_details(row["quote_id"])
        pdf_file = generate_pdf(row["quote_id"], row["name"], items[["item_name", "unit_price", "quantity"]].rename(columns={"item_name":"name", "unit_price":"price", "quantity":"qty"}).to_dict("records"), h["total_price"])
        return (dash.no_update,)*6 + (dcc.send_file(pdf_file), False, False)
    return (dash.no_update,)*7 + (True, True)

@app.callback([Output("nc-modal", "is_open"), Output("cust-select", "value")], [Input("btn-new-cust", "n_clicks"), Input("btn-save-nc", "n_clicks")], [State("nc-modal", "is_open"), State("nc-name", "value"), State("nc-street", "value"), State("nc-city", "value"), State("nc-zip", "value"), State("nc-phone", "value")])
def handle_new_customer(n1, n2, is_open, name, street, city, zip_code, phone):
    if ctx.triggered_id == "btn-new-cust": return True, dash.no_update
    if ctx.triggered_id == "btn-save-nc" and name:
        new_id = f"CUST-{1000 + len(MOCK_CUSTOMERS) + 1}"
        MOCK_CUSTOMERS.append({"customer_id": new_id, "name": name, "street": street or "", "city": city or "", "state": "TX", "zip": zip_code or "", "phone": phone or ""})
        return False, new_id
    return is_open, dash.no_update

@app.callback([Output("cart-store", "data"), Output("cart-list", "children"), Output("cart-total", "children")], [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks"), Input("edit-mode-store", "data")], [State("cart-store", "data"), State("part-select", "value"), State("part-qty", "value"), State("labor-select", "value"), State("labor-hrs", "value")])
def update_cart(b1, b2, edit_mode, cart, p_val, p_qty, l_val, l_hrs):
    trigger, cart = ctx.triggered_id, cart or []
    if trigger == "edit-mode-store": pass # Just refresh view
    elif trigger == "btn-add-part" and p_val:
        pid, name, cost, price = p_val.split("|")
        cart.append({"name": name, "type": "Part", "cost": float(cost), "price": float(price), "qty": float(p_qty or 1)})
    elif trigger == "btn-add-labor" and l_val:
        role, cost, rate = l_val.split("|")
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(cost), "price": float(rate), "qty": float(l_hrs or 0)})
    
    items = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']:.2f}", className="float-end fw-semibold")], className="border-bottom py-1 small") for i in cart]
    total = sum(i["price"] * i["qty"] for i in cart)
    return cart, items, f"${total:,.2f}"

@app.callback(Output("save-msg", "children"), Input("btn-finalize", "n_clicks"), [State("cust-select", "value"), State("job-type", "value"), State("estimator", "value"), State("cart-store", "data"), State("edit-mode-store", "data")])
def save_quote_cb(n, cust, jtype, est, cart, edit_mode):
    if not n: return ""
    missing = [k for k, v in [("Customer", cust), ("Job type", jtype), ("Estimator", est), ("Line items", cart)] if not v]
    if missing: return dbc.Alert("Missing: " + ", ".join(missing), color="danger", className="py-2")
    
    if edit_mode and edit_mode.get("mode") == "edit" and edit_mode.get("qid"):
        update_existing_quote(edit_mode["qid"], cust, jtype, est, cart)
        msg = "Quote updated."
    else:
        qid = save_new_quote(cust, jtype, est, cart)
        msg = f"Quote saved! ID: {qid}"
    return dbc.Alert(msg, color="success", className="py-2")

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
