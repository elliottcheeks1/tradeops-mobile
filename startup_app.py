import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import startup_db as db

db.init_db()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])
app.title = "TradeOps Pro"

# --- HELPER FUNCTIONS ---
def get_customer_options():
    df = db.get_customers()
    return [{"label": r['name'], "value": r['customer_id']} for _, r in df.iterrows()]

def get_parts_options():
    df = db.get_parts()
    # We embed cost in the value string so we can parse it secretly later
    # Format: "PartID|Name|Cost|Price"
    return [{"label": f"{r['name']} (${r['retail_price']})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in df.iterrows()]

# --- LAYOUTS ---

# TAB 1: OFFICE DASHBOARD (Shows Margins)
dashboard_layout = dbc.Container([
    html.H4("🏢 Office Dashboard (Margins Visible)"),
    html.Hr(),
    dbc.Button("Refresh Data", id="btn-refresh-dash", color="light", className="mb-3"),
    dash_table.DataTable(
        id='margin-table',
        columns=[
            {"name": "Client", "id": "client_name"},
            {"name": "Estimator", "id": "estimator"},
            {"name": "Revenue", "id": "total_price", "type": "numeric", "format": {"specifier": "$,.2f"}},
            {"name": "Cost", "id": "total_cost", "type": "numeric", "format": {"specifier": "$,.2f"}}, # VISIBLE HERE
            {"name": "Margin %", "id": "margin_percent", "type": "numeric", "format": {"specifier": ".1f"}}, # VISIBLE HERE
            {"name": "Status", "id": "status"},
        ],
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#e9ecef'},
        style_data_conditional=[
            {'if': {'filter_query': '{margin_percent} < 40', 'column_id': 'margin_percent'}, 'color': 'red', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{margin_percent} >= 40', 'column_id': 'margin_percent'}, 'color': 'green'}
        ]
    )
], fluid=True, className="mt-4")

# TAB 2: QUOTE BUILDER (Hides Cost)
quote_layout = dbc.Container([
    dbc.Row([
        # 1. CUSTOMER SELECTION
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("1. Customer"),
                dbc.CardBody([
                    dbc.Label("Select Existing Customer"),
                    dcc.Dropdown(id="cust-select", options=get_customer_options(), placeholder="Search Client..."),
                    html.Div("— OR —", className="text-center text-muted my-2"),
                    dbc.Button("Create New Customer", id="btn-open-new-cust", color="outline-primary", size="sm", className="w-100"),
                    
                    # New Customer Modal (Hidden by default)
                    dbc.Modal([
                        dbc.ModalHeader("Add New Customer"),
                        dbc.ModalBody([
                            dbc.Input(id="new-cust-name", placeholder="Name", className="mb-2"),
                            dbc.Input(id="new-cust-addr", placeholder="Address", className="mb-2"),
                            dbc.Input(id="new-cust-phone", placeholder="Phone", className="mb-2"),
                            dbc.Button("Save Customer", id="btn-save-cust", color="success", className="w-100")
                        ]),
                    ], id="modal-new-cust", is_open=False),
                    
                    html.Hr(),
                    dbc.Select(id="job-type", options=[
                        {"label": "Service", "value": "Service"}, {"label": "Install", "value": "Install"}
                    ], placeholder="Job Type", className="mb-2"),
                    dbc.Input(id="estimator-name", placeholder="Tech Name")
                ])
            ], className="h-100 shadow-sm")
        ], xs=12, lg=4, className="mb-4"),

        # 2. PARTS & LABOR (The "Misc" logic)
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("2. Add Items"),
                dbc.CardBody([
                    dbc.Tabs([
                        # CATALOG TAB
                        dbc.Tab(label="Catalog Part", children=[
                            html.Br(),
                            dcc.Dropdown(id="part-select", options=get_parts_options(), placeholder="Search Database..."),
                            dbc.Input(id="part-qty", type="number", placeholder="Qty", value=1, className="mt-2"),
                            dbc.Button("Add Catalog Item", id="btn-add-part", color="primary", className="w-100 mt-2")
                        ]),
                        # MISC TAB
                        dbc.Tab(label="Misc / Custom", children=[
                            html.Br(),
                            dbc.Input(id="misc-name", placeholder="Description (e.g. Home Depot Run)"),
                            dbc.Row([
                                # Tech inputs PRICE. Cost defaults to 0 if they don't know it.
                                dbc.Col(dbc.Input(id="misc-price", type="number", placeholder="Sell Price"), width=6),
                                dbc.Col(dbc.Input(id="misc-qty", type="number", placeholder="Qty", value=1), width=6),
                            ], className="mt-2"),
                            dbc.FormText("Office will adjust cost later.", className="text-muted"),
                            dbc.Button("Add Misc Item", id="btn-add-misc", color="warning", className="w-100 mt-2")
                        ])
                    ])
                ])
            ], className="h-100 shadow-sm")
        ], xs=12, lg=4, className="mb-4"),

        # 3. SUMMARY
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("3. Quote Summary"),
                dbc.CardBody([
                    html.Div(id="quote-list", style={"maxHeight": "250px", "overflowY": "auto"}),
                    html.Hr(),
                    # ONLY PRICE IS SHOWN HERE
                    html.H3(id="display-total", children="$0.00", className="text-end text-success"),
                    dbc.Button("Finalize Quote", id="btn-finalize", color="success", size="lg", className="w-100 mt-3")
                ])
            ], className="h-100 shadow-sm")
        ], xs=12, lg=4, className="mb-4")
    ])
], fluid=True, className="mt-3")

# --- APP INIT ---
app.layout = html.Div([
    dcc.Store(id="cart-store", data=[]),
    dbc.NavbarSimple(brand="TradeOps V2.1", color="dark", dark=True),
    dbc.Tabs([
        dbc.Tab(quote_layout, label="Tech: Quote Builder", tab_id="tab-quote"),
        dbc.Tab(dashboard_layout, label="Office: Margins", tab_id="tab-dash"),
    ], id="tabs", active_tab="tab-quote")
])

# --- CALLBACKS ---

# 1. Manage New Customer Modal
@app.callback(
    [Output("modal-new-cust", "is_open"), Output("cust-select", "options"), Output("cust-select", "value")],
    [Input("btn-open-new-cust", "n_clicks"), Input("btn-save-cust", "n_clicks")],
    [State("modal-new-cust", "is_open"), State("new-cust-name", "value"), 
     State("new-cust-addr", "value"), State("new-cust-phone", "value")]
)
def manage_customer(open_click, save_click, is_open, name, addr, phone):
    trigger = ctx.triggered_id
    if trigger == "btn-open-new-cust":
        return True, dash.no_update, dash.no_update
    
    if trigger == "btn-save-cust" and name:
        new_id = db.add_customer(name, addr, phone, "")
        opts = get_customer_options() # Reload options
        return False, opts, new_id # Auto-select the new guy
        
    return is_open, dash.no_update, dash.no_update

# 2. Add Items (Catalog vs Misc) & Update Cart
@app.callback(
    [Output("cart-store", "data"), Output("quote-list", "children"), Output("display-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-misc", "n_clicks"), Input("btn-finalize", "n_clicks")],
    [State("cart-store", "data"), 
     State("part-select", "value"), State("part-qty", "value"),
     State("misc-name", "value"), State("misc-price", "value"), State("misc-qty", "value")]
)
def update_cart(btn_cat, btn_misc, btn_fin, cart, part_str, p_qty, m_name, m_price, m_qty):
    trigger = ctx.triggered_id
    
    if trigger == "btn-finalize":
        return [], "Quote Saved!", "$0.00"

    # Add Catalog Item
    if trigger == "btn-add-part" and part_str:
        # Parse hidden data "ID|Name|Cost|Price"
        pid, name, cost, price = part_str.split("|")
        cart.append({
            "name": name, "type": "Part", 
            "cost": float(cost), "price": float(price), "qty": float(p_qty)
        })

    # Add Misc Item
    if trigger == "btn-add-misc" and m_name and m_price:
        cart.append({
            "name": f"Misc: {m_name}", "type": "Misc", 
            "cost": 0.0, # Default to 0 so tech doesn't worry about it
            "price": float(m_price), "qty": float(m_qty)
        })

    # Render List
    items_ui = []
    total = 0
    for i in cart:
        line_tot = i['price'] * i['qty']
        total += line_tot
        items_ui.append(html.Div([
            html.Span(f"{i['name']} (x{i['qty']})", className="fw-bold"),
            html.Span(f"${line_tot:,.2f}", className="float-end")
        ], className="border-bottom p-2"))
        
    return cart, items_ui, f"${total:,.2f}"

# 3. Finalize Quote to DB
@app.callback(
    Output("btn-finalize", "children"),
    Input("btn-finalize", "n_clicks"),
    [State("cust-select", "value"), State("job-type", "value"), State("estimator-name", "value"), State("cart-store", "data")]
)
def save_quote_callback(n, cust_id, jtype, est, cart):
    if not n or not cart or not cust_id: return "Finalize Quote"
    db.save_quote_v2(cust_id, jtype, est, cart)
    return "Saved!"

# 4. Refresh Office Dashboard
@app.callback(
    Output("margin-table", "data"),
    [Input("btn-refresh-dash", "n_clicks"), Input("tabs", "active_tab")]
)
def refresh_dashboard(n, tab):
    if tab == "tab-dash":
        return db.get_office_dashboard_data().to_dict('records')
    return dash.no_update

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)