import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import tradeops_v3_db as db
from fpdf import FPDF
import base64
import os
from datetime import datetime, timedelta

db.init_db()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])
app.title = "TradeOps Field V5"
server = app.server

# --- PDF GENERATION ENGINE ---
def generate_pdf(quote_id, version, customer_name, items, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Header
    pdf.cell(0, 10, f"Quote #{quote_id} (v{version})", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Customer: {customer_name}", ln=True)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.line(10, 40, 200, 40)
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Description", 1)
    pdf.cell(30, 10, "Qty", 1, align='C')
    pdf.cell(50, 10, "Price", 1, align='R')
    pdf.ln()
    
    # Items
    pdf.set_font("Arial", size=12)
    for item in items:
        pdf.cell(100, 10, str(item['name']), 1)
        pdf.cell(30, 10, str(item['qty']), 1, align='C')
        pdf.cell(50, 10, f"${item['price']:.2f}", 1, align='R')
        pdf.ln()
        
    # Total
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(130, 10, "Total Estimate:", align='R')
    pdf.cell(50, 10, f"${total:,.2f}", align='R')
    
    # Disclaimer
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 10, "This quote is valid for 30 days. Signature required for work to begin.")
    
    # Save to temp file
    filename = f"quote_{quote_id}_v{version}.pdf"
    pdf.output(filename)
    return filename

# --- LAYOUTS ---

# 1. HISTORY TAB (Replaces Analytics)
history_tab = dbc.Container([
    html.H4("📂 My Quotes", className="mt-3"),
    dbc.Button("↻ Refresh", id="btn-refresh-hist", color="light", size="sm", className="mb-2"),
    dash_table.DataTable(
        id='history-table',
        columns=[
            {"name": "Client", "id": "name"},
            {"name": "Date", "id": "created_at"},
            {"name": "Total", "id": "total_price", "type": "numeric", "format": {"specifier": "$,.0f"}},
            {"name": "Status", "id": "status"},
        ],
        style_cell={'textAlign': 'left', 'padding': '10px'},
        row_selectable='single'
    ),
    dbc.Row([
        dbc.Col(dbc.Button("📝 Edit / Update", id="btn-load-edit", color="warning", className="w-100", disabled=True), width=6),
        dbc.Col(dbc.Button("📄 Download PDF", id="btn-dl-pdf", color="info", className="w-100", disabled=True), width=6),
    ], className="mt-3"),
    dcc.Download(id="download-pdf-component")
], fluid=True)

# 2. QUOTE BUILDER (With Edit Logic)
quote_tab = dbc.Container([
    dcc.Store(id="edit-mode-store", data={"mode": "new", "qid": None, "ver": None}), # Tracks if editing
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
                        dbc.Row([
                            dbc.Col(dbc.Input(id="nc-city", placeholder="City"), width=6),
                            dbc.Col(dbc.Input(id="nc-zip", placeholder="Zip"), width=6),
                        ]),
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
                html.Div(id="save-msg", className="mt-2 text-center")
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3")
    ])
], fluid=True)

app.layout = html.Div([
    dcc.Store(id="cart-store", data=[]),
    dbc.NavbarSimple(brand="TradeOps Field V5", color="dark", dark=True),
    dbc.Tabs([
        dbc.Tab(history_tab, label="My Quotes", tab_id="tab-hist"),
        dbc.Tab(quote_tab, label="Quote Builder", tab_id="tab-quote"),
    ], id="tabs", active_tab="tab-hist")
])

# --- LOGIC ---

@app.callback(
    [Output("cust-select", "options"), Output("part-select", "options"), Output("labor-select", "options"), Output("history-table", "data")],
    [Input("tabs", "active_tab"), Input("btn-refresh-hist", "n_clicks")]
)
def load_data(tab, n):
    c_opts = [{"label": r['name'], "value": r['customer_id']} for _, r in db.get_customers().iterrows()]
    p_opts = [{"label": f"{r['name']} (${r['retail_price']})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in db.get_parts().iterrows()]
    l_opts = [{"label": f"{r['role']} (${r['bill_rate']}/hr)", "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}"} for _, r in db.get_labor().iterrows()]
    hist_data = db.get_tech_history().to_dict('records')
    return c_opts, p_opts, l_opts, hist_data

# --- NEW CUSTOMER ---
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

# --- CART MANAGEMENT ---
@app.callback(
    [Output("cart-store", "data"), Output("cart-list", "children"), Output("cart-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks"), Input("edit-mode-store", "data")],
    [State("cart-store", "data"), State("part-select", "value"), State("part-qty", "value"),
     State("labor-select", "value"), State("labor-hrs", "value")]
)
def update_cart(b1, b2, edit_data, cart, p_val, p_qty, l_val, l_hrs):
    trigger = ctx.triggered_id
    
    # If loading edit, cart is handled by the edit loader callback, but we need to ensure we don't clear it
    if trigger == "edit-mode-store":
        return dash.no_update, dash.no_update, dash.no_update

    if trigger == "btn-add-part" and p_val:
        pid, name, cost, price = p_val.split("|")
        cart.append({"name": name, "type": "Part", "cost": float(cost), "price": float(price), "qty": float(p_qty)})
    if trigger == "btn-add-labor" and l_val:
        role, cost, rate = l_val.split("|")
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(cost), "price": float(rate), "qty": float(l_hrs)})
        
    items = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']:.2f}", className="float-end")], className="border-bottom p-2") for i in cart]
    total = sum([i['price']*i['qty'] for i in cart])
    return cart, items, f"${total:,.2f}"

# --- SAVE QUOTE ---
@app.callback(
    Output("save-msg", "children"),
    Input("btn-finalize", "n_clicks"),
    [State("cust-select", "value"), State("job-type", "value"), State("estimator", "value"), 
     State("cart-store", "data"), State("edit-mode-store", "data")]
)
def save_quote(n, cust, jtype, est, cart, edit_mode):
    if not n or not cart: return ""
    
    if edit_mode['mode'] == 'edit':
        db.update_quote(edit_mode['qid'], edit_mode['ver'], cust, jtype, est, cart)
        return "Quote Updated!"
    else:
        qid = db.save_new_quote(cust, jtype, est, cart)
        return f"Saved! #{qid}"

# --- EDIT & PDF DOWNLOAD LOGIC ---
@app.callback(
    [Output("tabs", "active_tab"), Output("cust-select", "value", allow_duplicate=True),
     Output("job-type", "value"), Output("estimator", "value"), 
     Output("cart-store", "data", allow_duplicate=True), Output("edit-mode-store", "data"),
     Output("download-pdf-component", "data"),
     Output("btn-load-edit", "disabled"), Output("btn-dl-pdf", "disabled")],
    [Input("btn-load-edit", "n_clicks"), Input("btn-dl-pdf", "n_clicks"), Input("history-table", "selected_rows")],
    [State("history-table", "data")],
    prevent_initial_call=True
)
def handle_history_actions(btn_edit, btn_pdf, selected, data):
    trigger = ctx.triggered_id
    
    # Enable buttons when row selected
    if trigger == "history-table":
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, False, False

    if not selected: return dash.no_update
    row = data[selected[0]]
    
    # LOAD EDIT
    if trigger == "btn-load-edit":
        header, items_df = db.get_quote_details(row['quote_id'], row['version'])
        cart = items_df[['item_name', 'item_type', 'unit_cost', 'unit_price', 'quantity']].rename(
            columns={'item_name':'name', 'item_type':'type', 'unit_cost':'cost', 'unit_price':'price', 'quantity':'qty'}
        ).to_dict('records')
        
        edit_data = {"mode": "edit", "qid": row['quote_id'], "ver": row['version']}
        
        return "tab-quote", header['customer_id'], header['job_type'], header['estimator'], cart, edit_data, dash.no_update, dash.no_update, dash.no_update

    # DOWNLOAD PDF
    if trigger == "btn-dl-pdf":
        header, items_df = db.get_quote_details(row['quote_id'], row['version'])
        items = items_df[['item_name', 'unit_price', 'quantity']].rename(columns={'item_name':'name', 'unit_price':'price', 'quantity':'qty'}).to_dict('records')
        total = header['total_price']
        
        pdf_file = generate_pdf(row['quote_id'], row['version'], row['name'], items, total)
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dcc.send_file(pdf_file), dash.no_update, dash.no_update

    return dash.no_update

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
