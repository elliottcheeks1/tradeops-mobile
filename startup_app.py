import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import tradeops_v3_db as db
from fpdf import FPDF
from datetime import datetime, timedelta
import re
import os

db.init_db()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])
app.title = "TradeOps Field V6"
server = app.server

# --- PDF ENGINE ---
def generate_pdf(quote_id, customer_name, items, total):
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
    pdf.cell(0, 10, f"Quote #: {quote_id}", ln=True)
    pdf.cell(0, 10, f"Customer: {customer_name}", ln=True)
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
    
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 10, "Valid for 30 days.")
    
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', customer_name)
    filename = f"Quote_{clean_name}_{date_str}.pdf"
    pdf.output(filename)
    return filename

# --- LAYOUTS ---

# 1. FOLLOW-UP QUEUE (Restored from V4)
followup_tab = dbc.Container([
    html.H4("📞 Follow-Up Queue", className="mt-3"),
    dbc.Button("↻ Refresh", id="btn-refresh-fup", color="light", size="sm", className="mb-2"),
    dash_table.DataTable(
        id="fup-table", 
        columns=[
            {"name": "Client", "id": "name"},
            {"name": "Phone", "id": "phone"},
            {"name": "Status", "id": "followup_status"},
            {"name": "Due", "id": "next_followup_date"},
        ],
        row_selectable='single', 
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'fontWeight': 'bold'},
        page_size=10
    ),
    dbc.Button("Log Call / Update", id="btn-open-log", color="primary", className="mt-2 w-100", disabled=True),
    
    # Log Interaction Modal
    dbc.Modal([
        dbc.ModalHeader("Log Interaction"),
        dbc.ModalBody([
            dbc.Label("Outcome"),
            dbc.Select(id="log-outcome", options=[
                {"label": "Left Voicemail", "value": "Left VM"},
                {"label": "Spoke - Not Ready", "value": "Needs Call"},
                {"label": "Spoke - Sold!", "value": "Won"},
                {"label": "Lost/Not Interested", "value": "Lost"}
            ], value="Needs Call"),
            html.Br(),
            dbc.Label("Next Follow-Up Date"),
            dcc.DatePickerSingle(id="log-date", date=(datetime.now() + timedelta(days=2)).date(), display_format='YYYY-MM-DD'),
            html.Br(), html.Br(),
            dbc.Button("Save & Update", id="btn-save-log", color="success", className="w-100")
        ])
    ], id="modal-log", is_open=False)
], fluid=True)


# 2. HISTORY TAB (With Tech Filter)
history_tab = dbc.Container([
    html.H4("📂 Quote History", className="mt-3"),
    dbc.Row([
        dbc.Col(dbc.Input(id="hist-filter-input", placeholder="Filter by Estimator Name...", type="text"), width=8),
        dbc.Col(dbc.Button("Filter", id="btn-filter-hist", color="secondary", className="w-100"), width=4),
    ], className="mb-2"),
    
    dash_table.DataTable(
        id='history-table',
        columns=[
            {"name": "Client", "id": "name"},
            {"name": "Estimator", "id": "estimator"},
            {"name": "Total", "id": "total_price", "type": "numeric", "format": {"specifier": "$,.0f"}},
            {"name": "Status", "id": "status"},
        ],
        style_cell={'textAlign': 'left', 'padding': '10px'},
        row_selectable='single',
        page_size=10
    ),
    dbc.Row([
        dbc.Col(dbc.Button("📝 Edit Quote", id="btn-load-edit", color="warning", className="w-100", disabled=True), width=6),
        dbc.Col(dbc.Button("📄 Download PDF", id="btn-dl-pdf", color="info", className="w-100", disabled=True), width=6),
    ], className="mt-3"),
    dcc.Download(id="download-pdf-component")
], fluid=True)


# 3. QUOTE BUILDER
quote_tab = dbc.Container([
    dcc.Store(id="edit-mode-store", data={"mode": "new", "qid": None}),
    dbc.Row([
        dbc.Col([
            dbc.Card([dbc.CardHeader("1. Customer"), dbc.CardBody([
                dcc.Dropdown(id="cust-select", options=[], placeholder="Select Client"),
                html.Br(),
                dbc.Button("New Customer", id="btn-new-cust", size="sm", color="light", className="w-100"),
                dbc.Modal([
                    dbc.ModalHeader("New Customer"),
                    dbc.ModalBody([
                        dbc.Input(id="nc-name", placeholder="Company/Name", className="mb-2"),
                        dbc.Input(id="nc-street", placeholder="Street", className="mb-2"),
                        dbc.Input(id="nc-city", placeholder="City", className="mb-2"),
                        dbc.Input(id="nc-zip", placeholder="Zip", className="mb-2"),
                        dbc.Input(id="nc-phone", placeholder="Phone", className="mb-2"),
                        dbc.Button("Save", id="btn-save-nc", color="success", className="w-100")
                    ])
                ], id="nc-modal", is_open=False),
                html.Hr(),
                dbc.Select(id="job-type", options=[{"label": "Service", "value": "Service"}, {"label": "Install", "value": "Install"}], placeholder="Job Type", className="mb-2"),
                dbc.Input(id="estimator", placeholder="Estimator Name")
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3"),

        dbc.Col([
            dbc.Card([dbc.CardHeader("2. Items"), dbc.CardBody([
                dbc.Tabs([
                    dbc.Tab(label="Parts", children=[
                        html.Br(), dcc.Dropdown(id="part-select", options=[], placeholder="Search Catalog"),
                        dbc.Input(id="part-qty", type="number", placeholder="Qty", value=1, className="mt-2"),
                        dbc.Button("Add Part", id="btn-add-part", color="secondary", className="w-100 mt-2")
                    ]),
                    dbc.Tab(label="Labor", children=[
                        html.Br(), dbc.Select(id="labor-select", options=[], placeholder="Select Role"),
                        dbc.Input(id="labor-hrs", type="number", placeholder="Hours", className="mt-2"),
                        dbc.Button("Add Labor", id="btn-add-labor", color="secondary", className="w-100 mt-2")
                    ])
                ])
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3"),

        dbc.Col([
            dbc.Card([dbc.CardHeader("3. Summary"), dbc.CardBody([
                html.Div(id="cart-list", style={"maxHeight": "200px", "overflowY": "auto"}),
                html.Hr(),
                html.H3(id="cart-total", children="$0.00", className="text-end text-success"),
                dbc.Button("Finalize & Save", id="btn-finalize", color="success", size="lg", className="w-100 mt-2"),
                html.Div(id="save-msg", className="mt-2 text-center fw-bold")
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3")
    ])
], fluid=True)

app.layout = html.Div([
    dcc.Store(id="cart-store", data=[]),
    dbc.NavbarSimple(brand="TradeOps Field V6", color="dark", dark=True),
    dbc.Tabs([
        dbc.Tab(followup_tab, label="Follow-Up", tab_id="tab-fup"),
        dbc.Tab(history_tab, label="History", tab_id="tab-hist"),
        dbc.Tab(quote_tab, label="Builder", tab_id="tab-quote"),
    ], id="tabs", active_tab="tab-fup")
])

# --- LOGIC ---

# 1. LOAD DATA & FILTER HISTORY
@app.callback(
    [Output("cust-select", "options"), Output("part-select", "options"), Output("labor-select", "options"), Output("history-table", "data")],
    [Input("tabs", "active_tab"), Input("btn-filter-hist", "n_clicks"), Input("btn-refresh-hist", "n_clicks")],
    [State("hist-filter-input", "value")]
)
def load_data(tab, n_filter, n_refresh, filter_name):
    c_opts = [{"label": r['name'], "value": r['customer_id']} for _, r in db.get_customers().iterrows()]
    p_opts = [{"label": f"{r['name']} (${r['retail_price']})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in db.get_parts().iterrows()]
    l_opts = [{"label": f"{r['role']} (${r['bill_rate']}/hr)", "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}"} for _, r in db.get_labor().iterrows()]
    
    # Filter History
    hist_data = db.get_tech_history(estimator_name=filter_name).to_dict('records')
    
    return c_opts, p_opts, l_opts, hist_data

# 2. FOLLOW-UP LOGIC (Restored)
@app.callback(
    [Output("modal-log", "is_open"), Output("fup-table", "data"), Output("btn-open-log", "disabled")],
    [Input("btn-open-log", "n_clicks"), Input("btn-save-log", "n_clicks"), Input("tabs", "active_tab"), Input("btn-refresh-fup", "n_clicks"), Input("fup-table", "selected_rows")],
    [State("modal-log", "is_open"), State("fup-table", "data"), State("log-outcome", "value"), State("log-date", "date")]
)
def handle_followup(n_open, n_save, tab, n_refresh, selected, is_open, table_data, outcome, next_date):
    trigger = ctx.triggered_id
    
    # Enable button only if selected
    btn_disabled = True if not selected else False
    
    if trigger == "tabs" or trigger == "btn-refresh-fup":
        return False, db.get_followup_queue().to_dict('records'), True # Disable button on refresh

    if trigger == "fup-table":
        return is_open, dash.no_update, btn_disabled

    if trigger == "btn-open-log":
        return True, dash.no_update, btn_disabled
    
    if trigger == "btn-save-log" and selected:
        row = table_data[selected[0]]
        db.log_interaction(row['quote_id'], outcome, next_date)
        return False, db.get_followup_queue().to_dict('records'), True
        
    return is_open, dash.no_update, btn_disabled

# 3. HISTORY ACTIONS (EDIT / PDF) - FIXING ARITY
@app.callback(
    [Output("tabs", "active_tab", allow_duplicate=True), 
     Output("cust-select", "value", allow_duplicate=True),
     Output("job-type", "value"), 
     Output("estimator", "value"), 
     Output("cart-store", "data", allow_duplicate=True), 
     Output("edit-mode-store", "data"),
     Output("download-pdf-component", "data"),
     Output("btn-load-edit", "disabled"), 
     Output("btn-dl-pdf", "disabled")],
    [Input("btn-load-edit", "n_clicks"), Input("btn-dl-pdf", "n_clicks"), Input("history-table", "selected_rows")],
    [State("history-table", "data")],
    prevent_initial_call=True
)
def handle_history_actions(btn_edit, btn_pdf, selected, data):
    trigger = ctx.triggered_id
    
    # Enable buttons when row selected
    if trigger == "history-table":
        has_sel = True if selected else False
        # Return 9 outputs (dash.no_update for UI changes, False/True for buttons)
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, not has_sel, not has_sel)

    if not selected: 
        # Safety catch with correct arity
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, True, True)

    row = data[selected[0]]
    
    if trigger == "btn-load-edit":
        header, items_df = db.get_quote_details(row['quote_id'])
        cart = items_df[['item_name', 'item_type', 'unit_cost', 'unit_price', 'quantity']].rename(
            columns={'item_name':'name', 'item_type':'type', 'unit_cost':'cost', 'unit_price':'price', 'quantity':'qty'}
        ).to_dict('records')
        edit_data = {"mode": "edit", "qid": row['quote_id']}
        # Switch tab, load data, clear PDF
        return ("tab-quote", header['customer_id'], header['job_type'], header['estimator'], 
                cart, edit_data, dash.no_update, True, True)

    if trigger == "btn-dl-pdf":
        header, items_df = db.get_quote_details(row['quote_id'])
        items = items_df[['item_name', 'unit_price', 'quantity']].rename(columns={'item_name':'name', 'unit_price':'price', 'quantity':'qty'}).to_dict('records')
        pdf_file = generate_pdf(row['quote_id'], row['name'], items, header['total_price'])
        # Send file
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dcc.send_file(pdf_file), False, False)

    return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
            dash.no_update, dash.no_update, dash.no_update, True, True)

# 4. CUSTOMER & CART (Same as before)
@app.callback(
    [Output("nc-modal", "is_open"), Output("cust-select", "value")],
    [Input("btn-new-cust", "n_clicks"), Input("btn-save-nc", "n_clicks")],
    [State("nc-modal", "is_open"), State("nc-name", "value"), State("nc-street", "value"), State("nc-city", "value"), State("nc-zip", "value"), State("nc-phone", "value")]
)
def handle_cust(n1, n2, is_open, name, st, city, zipc, ph):
    if ctx.triggered_id == "btn-new-cust": return True, dash.no_update
    if ctx.triggered_id == "btn-save-nc" and name:
        return False, db.add_customer(name, st, city, "TX", zipc, ph)
    return is_open, dash.no_update

@app.callback(
    [Output("cart-store", "data"), Output("cart-list", "children"), Output("cart-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks"), Input("edit-mode-store", "data")],
    [State("cart-store", "data"), State("part-select", "value"), State("part-qty", "value"),
     State("labor-select", "value"), State("labor-hrs", "value")]
)
def update_cart(b1, b2, edit_data, cart, p_val, p_qty, l_val, l_hrs):
    trigger = ctx.triggered_id
    if trigger == "edit-mode-store": return dash.no_update, dash.no_update, dash.no_update

    if trigger == "btn-add-part" and p_val:
        pid, name, cost, price = p_val.split("|")
        cart.append({"name": name, "type": "Part", "cost": float(cost), "price": float(price), "qty": float(p_qty)})
    if trigger == "btn-add-labor" and l_val:
        role, cost, rate = l_val.split("|")
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(cost), "price": float(rate), "qty": float(l_hrs)})
        
    items = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']:.2f}", className="float-end")], className="border-bottom p-2") for i in cart]
    total = sum([i['price']*i['qty'] for i in cart])
    return cart, items, f"${total:,.2f}"

@app.callback(
    Output("save-msg", "children"),
    Input("btn-finalize", "n_clicks"),
    [State("cust-select", "value"), State("job-type", "value"), State("estimator", "value"), 
     State("cart-store", "data"), State("edit-mode-store", "data")]
)
def save_quote(n, cust, jtype, est, cart, edit_mode):
    if not n or not cart: return ""
    
    if edit_mode['mode'] == 'edit':
        db.update_existing_quote(edit_mode['qid'], cust, jtype, est, cart)
        return "Quote Updated!"
    else:
        qid = db.save_new_quote(cust, jtype, est, cart)
        return f"Saved! #{qid}"

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
