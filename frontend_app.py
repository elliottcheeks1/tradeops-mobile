import os
import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import requests

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")

def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"

# -------------------------------------------------------------------
# Dash App
# -------------------------------------------------------------------
external_stylesheets = [dbc.themes.MINTY, dbc.icons.BOOTSTRAP]

dash_app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    requests_pathname_prefix="/app/",
)
app = dash_app

# -------------------------------------------------------------------
# Components
# -------------------------------------------------------------------
def kpi_card(title, value, subtitle, icon_class, color="success"):
    return dbc.Card(
        dbc.CardBody([
            html.Div([
                html.H6(title, className="text-uppercase text-muted mb-2", style={"fontSize": "0.75rem"}),
                html.Div([
                    html.H2(value, className=f"text-{color} mb-0"),
                    html.I(className=f"{icon_class} text-{color} opacity-50 display-6 position-absolute top-0 end-0 mt-3 me-3")
                ], className="position-relative")
            ]),
            html.Small(subtitle, className="text-muted")
        ]),
        className="shadow-sm border-0 h-100"
    )

def navbar():
    return dbc.Navbar(
        dbc.Container(
            [
                html.A(
                    dbc.Row(
                        [
                            dbc.Col(html.I(className="bi bi-tools text-white fs-4")),
                            dbc.Col(dbc.NavbarBrand("TradeOps Enterprise | Dashboard", className="ms-2 fw-bold text-white")),
                        ],
                        align="center",
                        className="g-0",
                    ),
                    href="/app",
                    style={"textDecoration": "none"},
                ),
            ],
            fluid=True,
        ),
        color="#20c997",
        dark=True,
        className="mb-4 shadow-sm py-3",
    )

# -------------------------------------------------------------------
# Views
# -------------------------------------------------------------------
def pipeline_view():
    return html.Div([
        # KPIs
        dbc.Row([
            dbc.Col(kpi_card("Won Revenue", "$14,828", "2 Deals", "bi bi-cash-stack"), md=3),
            dbc.Col(kpi_card("Open Pipeline", "$8,500", "1 Active", "bi bi-funnel", color="warning"), md=3),
            dbc.Col(kpi_card("Win Rate", "66.7%", "Of closed deals", "bi bi-trophy", color="info"), md=3),
            dbc.Col(kpi_card("Avg Margin", "54.2%", "On won jobs", "bi bi-percent"), md=3),
        ], className="mb-4"),

        # Table & Actions
        dbc.Card([
            dbc.CardHeader("Quotes List", className="bg-white border-bottom-0 fw-bold"),
            dbc.CardBody([
                dash_table.DataTable(
                    id="quotes-table",
                    columns=[
                        {"name": "ID", "id": "id"},
                        {"name": "Client", "id": "customer_name"},
                        {"name": "Status", "id": "status"},
                        {"name": "Total", "id": "total_price", "type": "numeric", "format": dash_table.FormatTemplate.money(0)},
                        {"name": "Date", "id": "created_at"},
                    ],
                    style_as_list_view=True,
                    row_selectable="single",
                    style_header={"fontWeight": "bold", "backgroundColor": "#f8f9fa", "borderBottom": "2px solid #dee2e6"},
                    style_cell={"padding": "12px", "fontSize": "14px"},
                    style_data_conditional=[
                        {'if': {'filter_query': '{status} = "won"'}, 'color': '#198754', 'fontWeight': 'bold'},
                        {'if': {'filter_query': '{status} = "lost"'}, 'color': '#dc3545'},
                    ],
                    page_size=10
                ),
                html.Div(id="table-actions", className="mt-3", children=[
                    dbc.Button("Edit Quote", id="btn-edit-quote", color="primary", size="sm", className="me-2", disabled=True),
                    dbc.Button("Mark Won", id="btn-mark-won", color="success", size="sm", className="me-2", disabled=True),
                ])
            ], className="p-0")
        ], className="shadow-sm border-0 mb-4"),

        # Notes Section (Appears on selection)
        html.Div(id="notes-container", style={"display": "none"}, children=[
             dbc.Card([
                dbc.CardHeader(id="notes-header", children="Notes", className="text-white fw-bold", style={"backgroundColor": "#f06595"}),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H6("History", className="text-muted small"),
                            html.Div(id="notes-history", style={"maxHeight": "200px", "overflowY": "auto"}, className="mb-3 border p-2 bg-light rounded")
                        ], md=8),
                        dbc.Col([
                            html.H6("Add Note", className="text-muted small"),
                            dbc.Textarea(id="new-note-input", placeholder="Enter notes...", rows=3, className="mb-2"),
                            dbc.Button("Add Note", id="btn-add-note", color="danger", size="sm", className="w-100", style={"backgroundColor": "#f06595", "borderColor": "#f06595"})
                        ], md=4)
                    ])
                ])
             ], className="shadow-sm border-0")
        ])
    ])

def quote_builder_view():
    return html.Div([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("1. Customer & Job", className="bg-white fw-bold"),
                    dbc.CardBody([
                        dbc.Label("Customer Name"),
                        dbc.Input(id="qb-customer", placeholder="e.g. Burger King", className="mb-3"),
                        dbc.Label("Job Title"),
                        dbc.Input(id="qb-title", placeholder="e.g. Grease Trap Repair", className="mb-3"),
                        dbc.Row([
                            dbc.Col([dbc.Label("Status"), dbc.Select(id="qb-status", options=[
                                {"label": "Draft", "value": "draft"},
                                {"label": "Sent", "value": "sent"},
                                {"label": "Won", "value": "won"},
                            ], value="draft")], md=6),
                             dbc.Col([dbc.Label("Estimator"), dbc.Input(id="qb-estimator", value="Elliott", disabled=True)], md=6),
                        ])
                    ])
                ], className="shadow-sm border-0 h-100")
            ], md=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("2. Line Items", className="bg-white fw-bold"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(dbc.Input(id="item-1-desc", placeholder="Description"), md=6),
                            dbc.Col(dbc.Input(id="item-1-qty", type="number", placeholder="Qty", value=1), md=2),
                            dbc.Col(dbc.Input(id="item-1-price", type="number", placeholder="Price", value=0), md=4),
                        ], className="mb-2"),
                         dbc.Row([
                            dbc.Col(dbc.Input(id="item-2-desc", placeholder="Description"), md=6),
                            dbc.Col(dbc.Input(id="item-2-qty", type="number", placeholder="Qty", value=1), md=2),
                            dbc.Col(dbc.Input(id="item-2-price", type="number", placeholder="Price", value=0), md=4),
                        ], className="mb-2"),
                        html.Hr(),
                        html.H4(id="qb-total-display", className="text-end text-success", children="$0.00")
                    ])
                ], className="shadow-sm border-0 h-100")
            ], md=5),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("3. Save", className="bg-white fw-bold"),
                    dbc.CardBody([
                        dcc.Input(id="qb-quote-id", type="hidden"),
                        dbc.Button("Finalize & Save", id="btn-save-quote", color="success", className="w-100 py-3 fw-bold fs-5"),
                        html.Div(id="qb-save-msg", className="mt-2 text-center small")
                    ])
                ], className="shadow-sm border-0 h-100")
            ], md=3)
        ])
    ])

# -------------------------------------------------------------------
# Layout & Callbacks
# -------------------------------------------------------------------
dash_app.layout = html.Div([
    dcc.Store(id="quotes-store"),
    dcc.Interval(id="auto-refresh", interval=30*1000, n_intervals=0),
    navbar(),
    dbc.Container([
        dbc.Tabs([
            dbc.Tab(pipeline_view(), label="CRM & Pipeline", tab_id="tab-pipeline", labelClassName="text-dark fw-bold"),
            dbc.Tab(quote_builder_view(), label="Quote Builder", tab_id="tab-builder", labelClassName="text-dark fw-bold"),
        ], id="main-tabs", active_tab="tab-pipeline", className="mb-4"),
    ], fluid=True)
], style={"backgroundColor": "#f4f6f9", "minHeight": "100vh"})

@dash_app.callback(
    Output("quotes-store", "data"),
    [Input("auto-refresh", "n_intervals"), Input("main-tabs", "active_tab")],
)
def load_data(_n, _tab):
    try:
        resp = requests.get(api_url("/quotes"), timeout=4)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return []

@dash_app.callback(
    Output("quotes-table", "data"),
    Input("quotes-store", "data")
)
def update_table(data):
    if not data: return []
    df = pd.DataFrame(data)
    if "created_at" in df.columns:
        df["created_at"] = df["created_at"].astype(str).str.slice(0, 10)
    return df.to_dict("records")

@dash_app.callback(
    [Output("btn-edit-quote", "disabled"), Output("btn-mark-won", "disabled"),
     Output("notes-container", "style"), Output("notes-header", "children"),
     Output("notes-history", "children"), Output("new-note-input", "value")],
    [Input("quotes-table", "selected_rows"), Input("btn-add-note", "n_clicks")],
    [State("quotes-table", "data"), State("new-note-input", "value")]
)
def handle_selection(selected_rows, add_note_click, table_data, new_note_text):
    trigger = ctx.triggered_id
    if not selected_rows:
        return True, True, {"display": "none"}, "Notes", [], ""

    row_idx = selected_rows[0]
    row = table_data[row_idx]
    quote_id = row["id"]
    customer = row.get("customer_name", "Unknown")

    if trigger == "btn-add-note" and new_note_text:
        try:
            requests.post(api_url(f"/quotes/{quote_id}/notes"), json={"content": new_note_text, "author": "Elliott"})
            new_note_text = "" # Clear input on success
        except:
            pass
    
    notes_display = []
    try:
        resp = requests.get(api_url(f"/quotes/{quote_id}/notes"))
        if resp.status_code == 200:
            notes = resp.json()
            for n in notes:
                notes_display.append(
                    html.Div([
                        html.Small(f"{n['created_at'][:10]} - {n['author']}:", className="fw-bold text-muted"),
                        html.Div(n['content'], className="ms-2")
                    ], className="mb-2 border-bottom pb-1")
                )
        else:
            notes_display = [html.Div("No notes yet.")]
    except:
        notes_display = [html.Div("Error loading notes.")]

    return False, False, {"display": "block"}, f"Notes: {customer}", notes_display, new_note_text

@dash_app.callback(
    Output("quotes-store", "data", allow_duplicate=True),
    Input("btn-mark-won", "n_clicks"),
    State("quotes-table", "selected_rows"),
    State("quotes-table", "data"),
    prevent_initial_call=True
)
def mark_won(n_clicks, selected, data):
    if not selected: return dash.no_update
    row = data[selected[0]]
    requests.put(api_url(f"/quotes/{row['id']}"), json={"status": "won"})
    return requests.get(api_url("/quotes")).json() # Refresh store

@dash_app.callback(
    [Output("main-tabs", "active_tab"), Output("qb-quote-id", "value"),
     Output("qb-customer", "value"), Output("qb-title", "value"), Output("qb-status", "value")],
    Input("btn-edit-quote", "n_clicks"),
    State("quotes-table", "selected_rows"),
    State("quotes-table", "data"),
    prevent_initial_call=True
)
def edit_quote(n_clicks, selected, data):
    if not selected: return dash.no_update
    row = data[selected[0]]
    return "tab-builder", row["id"], row.get("customer_name", ""), row.get("title", ""), row.get("status", "draft")

@dash_app.callback(
    [Output("qb-save-msg", "children"), Output("quotes-store", "data", allow_duplicate=True)],
    Input("btn-save-quote", "n_clicks"),
    [State("qb-quote-id", "value"), State("qb-customer", "value"),
     State("qb-title", "value"), State("qb-status", "value"),
     State("item-1-desc", "value"), State("item-1-qty", "value"), State("item-1-price", "value"),
     State("item-2-desc", "value"), State("item-2-qty", "value"), State("item-2-price", "value")],
    prevent_initial_call=True
)
def save_quote_builder(n_clicks, q_id, cust, title, status, i1d, i1q, i1p, i2d, i2q, i2p):
    items = []
    if i1d: items.append({"description": i1d, "qty": float(i1q or 0), "unit_price": float(i1p or 0)})
    if i2d: items.append({"description": i2d, "qty": float(i2q or 0), "unit_price": float(i2p or 0)})
    
    payload = {
        "customer_id": "cust-demo",
        "location_id": "loc-demo",
        "title": title or "New Job",
        "line_items": items,
        "status": status
    }
    
    try:
        if q_id:
            requests.put(api_url(f"/quotes/{q_id}"), json=payload)
            msg = dbc.Alert("Updated!", color="success")
        else:
            requests.post(api_url("/quotes"), json=payload)
            msg = dbc.Alert("Created!", color="success")
        return msg, requests.get(api_url("/quotes")).json()
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger"), dash.no_update

@dash_app.callback(
    Output("qb-total-display", "children"),
    [Input("item-1-qty", "value"), Input("item-1-price", "value"),
     Input("item-2-qty", "value"), Input("item-2-price", "value")]
)
def calc_total(q1, p1, q2, p2):
    t = (float(q1 or 0) * float(p1 or 0)) + (float(q2 or 0) * float(p2 or 0))
    return f"${t:,.2f}"
