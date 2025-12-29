import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import tradeops_v3_db as db

db.init_db()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])
app.title = "TradeOps V3"

# --- HELPERS ---
def get_cust_opts(): return [{"label": r['name'], "value": r['customer_id']} for _, r in db.get_customers().iterrows()]
def get_part_opts(): return [{"label": f"{r['name']} (${r['retail_price']})", "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}"} for _, r in db.get_parts().iterrows()]
def get_labor_opts(): return [{"label": f"{r['role']} (${r['bill_rate']}/hr)", "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}"} for _, r in db.get_labor().iterrows()]

# --- LAYOUTS ---

# 1. FOLLOW-UP QUEUE (Gap B1)
followup_tab = dbc.Container([
    html.H4("📞 Follow-Up Queue", className="mt-3"),
    dash_table.DataTable(id="fup-table", row_selectable='single', style_table={'overflowX': 'auto'}),
    dbc.Button("Log Call & Reschedule", id="btn-log-call", color="primary", className="mt-2", disabled=True)
], fluid=True)

# 2. QUOTE BUILDER (Mobile Optimized)
quote_tab = dbc.Container([
    dbc.Row([
        # Customer
        dbc.Col([
            dbc.Card([dbc.CardHeader("1. Customer"), dbc.CardBody([
                dcc.Dropdown(id="cust-select", options=get_cust_opts(), placeholder="Select Client"),
                html.Br(),
                dbc.Button("New Client", id="btn-new-cust", size="sm", color="light", className="w-100"),
                dbc.Modal([
                    dbc.ModalHeader("New Customer"),
                    dbc.ModalBody([
                        dbc.Input(id="nc-name", placeholder="Name", className="mb-2"),
                        dbc.Input(id="nc-addr", placeholder="Address", className="mb-2"),
                        dbc.Input(id="nc-phone", placeholder="Phone", className="mb-2"),
                        dbc.Button("Save", id="btn-save-nc", color="success", className="w-100")
                    ])
                ], id="nc-modal", is_open=False),
                html.Hr(),
                dbc.Select(id="job-type", options=[{"label": "Service", "value": "Service"}, {"label": "Install", "value": "Install"}], placeholder="Job Type", className="mb-2"),
                dbc.Input(id="estimator", placeholder="Estimator Name")
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3"),

        # Items (Parts + Labor)
        dbc.Col([
            dbc.Card([dbc.CardHeader("2. Items"), dbc.CardBody([
                dbc.Tabs([
                    dbc.Tab(label="Parts", children=[
                        html.Br(), dcc.Dropdown(id="part-select", options=get_part_opts(), placeholder="Search Catalog"),
                        dbc.Input(id="part-qty", type="number", placeholder="Qty", value=1, className="mt-2"),
                        dbc.Button("Add Part", id="btn-add-part", color="secondary", className="w-100 mt-2")
                    ]),
                    dbc.Tab(label="Labor", children=[
                        html.Br(), dbc.Select(id="labor-select", options=get_labor_opts(), placeholder="Select Role"),
                        dbc.Input(id="labor-hrs", type="number", placeholder="Hours", className="mt-2"),
                        dbc.Button("Add Labor", id="btn-add-labor", color="secondary", className="w-100 mt-2")
                    ])
                ])
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3"),

        # Summary
        dbc.Col([
            dbc.Card([dbc.CardHeader("3. Summary"), dbc.CardBody([
                html.Div(id="cart-list", style={"maxHeight": "200px", "overflowY": "auto"}),
                html.Hr(),
                html.H3(id="cart-total", children="$0.00", className="text-end text-success"),
                dbc.Button("Finalize Quote", id="btn-finalize", color="success", size="lg", className="w-100 mt-2")
            ])], className="h-100")
        ], xs=12, lg=4, className="mb-3")
    ])
], fluid=True)

# 3. ANALYTICS DASHBOARD (Gap D)
analytics_tab = dbc.Container([
    html.H4("📊 Business Performance", className="mt-3"),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H6("Total Revenue"), html.H2(id="kpi-rev")])), width=6, lg=3),
        dbc.Col(dbc.Card(dbc.CardBody([html.H6("Close Rate"), html.H2(id="kpi-close")])), width=6, lg=3),
    ], className="mb-4"),
    dcc.Graph(id="chart-pipeline")
], fluid=True)

app.layout = html.Div([
    dcc.Store(id="cart-store", data=[]),
    dbc.NavbarSimple(brand="TradeOps V3.0", color="dark", dark=True),
    dbc.Tabs([
        dbc.Tab(followup_tab, label="Follow-Up", tab_id="tab-fup"),
        dbc.Tab(quote_tab, label="New Quote", tab_id="tab-quote"),
        dbc.Tab(analytics_tab, label="Analytics", tab_id="tab-anl"),
    ], id="tabs", active_tab="tab-fup")
])

# --- LOGIC ---

@app.callback(
    [Output("nc-modal", "is_open"), Output("cust-select", "options"), Output("cust-select", "value")],
    [Input("btn-new-cust", "n_clicks"), Input("btn-save-nc", "n_clicks")],
    [State("nc-modal", "is_open"), State("nc-name", "value"), State("nc-addr", "value"), State("nc-phone", "value")]
)
def handle_customer(n1, n2, is_open, name, addr, phone):
    trigger = ctx.triggered_id
    if trigger == "btn-new-cust": return True, dash.no_update, dash.no_update
    if trigger == "btn-save-nc" and name:
        new_id = db.add_customer(name, addr, phone)
        return False, get_cust_opts(), new_id
    return is_open, dash.no_update, dash.no_update

@app.callback(
    [Output("cart-store", "data"), Output("cart-list", "children"), Output("cart-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks"), Input("btn-finalize", "n_clicks")],
    [State("cart-store", "data"), State("part-select", "value"), State("part-qty", "value"),
     State("labor-select", "value"), State("labor-hrs", "value")]
)
def update_cart(b_part, b_lab, b_fin, cart, part_val, p_qty, lab_val, l_hrs):
    trigger = ctx.triggered_id
    if trigger == "btn-finalize": return [], "Quote Saved!", "$0.00"

    if trigger == "btn-add-part" and part_val:
        pid, name, cost, price = part_val.split("|")
        cart.append({"name": name, "type": "Part", "cost": float(cost), "price": float(price), "qty": float(p_qty)})

    if trigger == "btn-add-labor" and lab_val:
        role, cost, rate = lab_val.split("|")
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(cost), "price": float(rate), "qty": float(l_hrs)})

    # Render
    items = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']:.2f}", className="float-end")], className="border-bottom p-2") for i in cart]
    total = sum([i['price']*i['qty'] for i in cart])
    return cart, items, f"${total:,.2f}"

@app.callback(Output("btn-finalize", "children"), Input("btn-finalize", "n_clicks"),
              [State("cust-select", "value"), State("job-type", "value"), State("estimator", "value"), State("cart-store", "data")])
def save_quote(n, cust, jtype, est, cart):
    if n and cart and cust:
        db.save_quote(cust, jtype, est, cart)
        return "Saved!"
    return "Finalize Quote"

@app.callback(
    [Output("fup-table", "data"), Output("kpi-rev", "children"), Output("kpi-close", "children"), Output("chart-pipeline", "figure")],
    Input("tabs", "active_tab")
)
def refresh_data(tab):
    # 1. Refresh Follow-Up
    fup_data = db.get_followup_queue().to_dict('records')
    
    # 2. Refresh Analytics
    df = db.get_analytics()
    if df.empty: return fup_data, "$0", "0%", {}
    
    rev = df[df['status']=='Won']['total_price'].sum()
    wins = len(df[df['status']=='Won'])
    total = len(df)
    close_rate = (wins/total * 100) if total > 0 else 0
    
    fig = px.pie(df, names='status', values='total_price', title="Revenue by Status", hole=0.4)
    
    return fup_data, f"${rev:,.0f}", f"{close_rate:.1f}%", fig

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
