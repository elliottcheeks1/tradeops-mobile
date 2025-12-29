import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime, timedelta
import startup_db as db

# Initialize DB (Will create tables in Cloud if missing)
db.init_db()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP])
app.title = "TradeOps V2"
server = app.server  # <--- THIS IS REQUIRED FOR RENDER

# --- HELPER COMPONENTS ---
def get_labor_dropdown():
    df = db.get_labor_rates()
    return [{"label": f"{r['role']} (Bill: ${r['bill_rate']}/hr)", "value": r['role']} for _, r in df.iterrows()]

# --- LAYOUTS ---
# TAB 1: FOLLOW-UP QUEUE
followup_layout = dbc.Container([
    dbc.Row([dbc.Col([html.H4("📞 Morning Follow-Up Queue", className="text-primary"), html.P("Quotes due for contact today.", className="text-muted")])]),
    html.Br(),
    dash_table.DataTable(id='followup-table', row_selectable='single', style_table={'overflowX': 'auto'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'}, style_cell={'textAlign': 'left', 'padding': '10px'},
        columns=[{"name": "Client", "id": "client_name"}, {"name": "Value", "id": "total_price"}, {"name": "Status", "id": "followup_status"}, {"name": "Due", "id": "next_followup_date"}]),
    html.Br(),
    dbc.Card(id="action-card", children=[
        dbc.CardHeader("Log Activity"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([dbc.Label("Outcome"), dbc.Select(id="fup-outcome", options=[{"label": "Left Voicemail", "value": "Left VM"}, {"label": "Spoke - Not Interested", "value": "Lost"}, {"label": "Spoke - Booked", "value": "Won"}])], width=4),
                dbc.Col([dbc.Label("Next Follow-Up"), dcc.DatePickerSingle(id="fup-next-date", date=(datetime.now() + timedelta(days=3)).date())], width=4),
                dbc.Col([html.Br(), dbc.Button("Log Interaction", id="btn-log-fup", color="primary", className="w-100")], width=4)
            ])
        ])
    ], style={"display": "none"})
], fluid=True, className="mt-4")

# TAB 2: QUOTE BUILDER (Mobile Optimized)
quote_layout = dbc.Container([
    dbc.Row([
        # COLUMN 1: Job Setup
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("1. Job Setup"),
                dbc.CardBody([
                    dbc.Label("Client Info", className="fw-bold"),
                    dbc.Input(id="client-name", placeholder="Client Name", className="mb-3"),
                    dbc.Select(id="job-type", options=[
                        {"label": "Service Call", "value": "Service"},
                        {"label": "New Install", "value": "Install"},
                        {"label": "Emergency", "value": "Emergency"}
                    ], placeholder="Select Job Type", className="mb-3"),
                    dbc.Input(id="estimator-name", placeholder="Estimator Name", className="mb-3")
                ])
            ], className="h-100 shadow-sm") # h-100 makes cards same height on desktop
        ], xs=12, lg=4, className="mb-4"), # xs=12 stacks it on mobile
        
        # COLUMN 2: Labor & Materials
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("2. Add Line Items"),
                dbc.CardBody([
                    dbc.Tabs([
                        dbc.Tab(label="Labor", children=[
                            html.Br(),
                            dbc.Label("Role"),
                            dbc.Select(id="labor-role-select", options=get_labor_dropdown(), placeholder="Select Role"),
                            html.Br(),
                            dbc.Label("Hours"),
                            dbc.Input(id="labor-hours", type="number", placeholder="0", className="mb-3"),
                            dbc.Button("Add Labor", id="btn-add-labor", color="primary", outline=True, className="w-100")
                        ]),
                        dbc.Tab(label="Parts", children=[
                            html.Br(),
                            dbc.Label("Part Name"),
                            dbc.Input(id="mat-name", placeholder="e.g. 1/2 inch copper"),
                            html.Br(),
                            dbc.Row([
                                dbc.Col([dbc.Label("Cost"), dbc.Input(id="mat-cost", type="number", placeholder="$0.00")], width=6),
                                dbc.Col([dbc.Label("Sell Price"), dbc.Input(id="mat-price", type="number", placeholder="$0.00")], width=6),
                            ], className="mb-3"),
                            dbc.Button("Add Part", id="btn-add-mat", color="primary", outline=True, className="w-100")
                        ])
                    ])
                ])
            ], className="h-100 shadow-sm")
        ], xs=12, lg=4, className="mb-4"),
        
        # COLUMN 3: Summary
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("3. Review & Save"),
                dbc.CardBody([
                    html.H5("Quote Summary", className="card-title"),
                    html.Hr(),
                    html.Div(id="quote-preview-list", style={"maxHeight": "200px", "overflowY": "auto"}),
                    html.Hr(),
                    html.H2(id="live-quote-total", children="$0.00", className="text-end text-success fw-bold"),
                    dbc.Button("Save Quote", id="btn-save-quote", color="success", size="lg", className="w-100 mt-3 shadow")
                ])
            ], className="h-100 shadow-sm")
        ], xs=12, lg=4, className="mb-4")
    ])
], fluid=True, className="mt-3")
# TAB 3: SETTINGS
settings_layout = dbc.Container([html.H4("⚙️ Settings"), dash_table.DataTable(data=db.get_labor_rates().to_dict('records'), columns=[{"name": "Role", "id": "role"}, {"name": "Bill Rate", "id": "bill_rate"}])], fluid=True, className="mt-4")

app.layout = html.Div([dcc.Store(id='cart-store', data=[]), dcc.Interval(id='refresh-timer', interval=5000, n_intervals=0), dbc.NavbarSimple(brand="TradeOps V2 Cloud", color="dark", dark=True), dbc.Tabs([dbc.Tab(followup_layout, label="Follow-Up Queue", tab_id="tab-queue"), dbc.Tab(quote_layout, label="New Quote", tab_id="tab-quote"), dbc.Tab(settings_layout, label="Settings", tab_id="tab-settings")], id="main-tabs", active_tab="tab-quote")])

# --- CALLBACKS ---
@app.callback(Output("followup-table", "data"), [Input("refresh-timer", "n_intervals"), Input("main-tabs", "active_tab")])
def refresh_queue(n, tab):
    if tab == "tab-queue": return db.get_followup_queue().to_dict('records')
    return dash.no_update

@app.callback(Output("action-card", "style"), Input("followup-table", "selected_rows"))
def show_action_card(selected): return {"display": "block"} if selected else {"display": "none"}

@app.callback([Output("cart-store", "data"), Output("quote-preview-list", "children"), Output("live-quote-total", "children"), Output("btn-save-quote", "children")], [Input("btn-add-labor", "n_clicks"), Input("btn-add-mat", "n_clicks"), Input("btn-save-quote", "n_clicks")], [State("cart-store", "data"), State("labor-role-select", "value"), State("labor-hours", "value"), State("mat-name", "value"), State("mat-cost", "value"), State("mat-price", "value"), State("client-name", "value"), State("job-type", "value"), State("estimator-name", "value")])
def update_cart(btn_lab, btn_mat, btn_save, cart, role, hours, m_name, m_cost, m_price, client, j_type, est):
    trigger = ctx.triggered_id
    if trigger == "btn-save-quote":
        db.save_quote(client, j_type, est, cart)
        return [], "Quote Saved!", "$0.00", "Saved!"
    if trigger == "btn-add-labor" and role:
        r = db.get_labor_rates(); r = r[r['role'] == role].iloc[0]
        cart.append({"name": f"Labor: {role}", "type": "Labor", "cost": float(r['base_cost']), "price": float(r['bill_rate']), "qty": float(hours)})
    if trigger == "btn-add-mat": cart.append({"name": m_name, "type": "Material", "cost": float(m_cost), "price": float(m_price), "qty": 1})
    
    total = sum([i['price'] * i['qty'] for i in cart])
    preview = [html.Div([html.Span(f"{i['name']} (x{i['qty']})"), html.Span(f"${i['price']*i['qty']}", className="float-end")], className="border-bottom p-1") for i in cart]
    return cart, preview, f"${total:,.2f}", "Save Quote"

@app.callback(Output("btn-log-fup", "children"), Input("btn-log-fup", "n_clicks"), [State("followup-table", "selected_rows"), State("followup-table", "data"), State("fup-outcome", "value"), State("fup-next-date", "date")])
def log_fup(n, sel, data, out, date):
    if n and sel:
        row = data[sel[0]]
        db.update_followup(row['quote_id'], row['version'], out, date)
        return "Saved!"
    return "Log Interaction"

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)