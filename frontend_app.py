# frontend_app.py
import os
import requests
from datetime import datetime

import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc



# ==============================
# CONFIG
# ==============================
API_BASE = os.getenv("TRADEOPS_API_BASE", "https://tradeops-mobile.onrender.com")

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
)
server = app.server  # for gunicorn

# ==============================
# MOCK DATA (Catalog + Customers)
# ==============================

MOCK_CUSTOMERS = [
    {"id": 1, "name": "Mrs. Jones - Main St"},
    {"id": 2, "name": "ACME Rentals"},
    {"id": 3, "name": "Sunrise Apartments"},
]

MOCK_PARTS = [
    {"id": 101, "name": "HVAC Tune-Up", "category": "Service", "cost": 20, "price": 89},
    {"id": 102, "name": "16 SEER AC Unit", "category": "Install", "cost": 1800, "price": 2800},
    {"id": 103, "name": "Water Heater Install", "category": "Install", "cost": 600, "price": 1350},
    {"id": 104, "name": "Panel Upgrade 200A", "category": "Install", "cost": 800, "price": 2100},
    {"id": 105, "name": "Drain Cleaning", "category": "Service", "cost": 10, "price": 225},
    {"id": 106, "name": "Smart Thermostat", "category": "Service", "cost": 80, "price": 325},
    {"id": 107, "name": "EV Charger Install", "category": "Install", "cost": 300, "price": 1200},
]

MOCK_LABOR_ROLES = [
    {"role": "Junior Tech", "base_cost": 25, "bill_rate": 75},
    {"role": "Senior Tech", "base_cost": 40, "bill_rate": 125},
    {"role": "Installer", "base_cost": 35, "bill_rate": 110},
]


def customer_options():
    return [{"label": c["name"], "value": c["id"]} for c in MOCK_CUSTOMERS]


def part_options():
    return [
        {
            "label": f"{p['name']} (${p['price']})",
            "value": f"{p['id']}|{p['name']}|{p['cost']}|{p['price']}",
        }
        for p in MOCK_PARTS
    ]


def labor_options():
    return [
        {
            "label": f"{r['role']} (${r['bill_rate']}/hr)",
            "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}",
        }
        for r in MOCK_LABOR_ROLES
    ]


# ==============================
# API HELPERS
# ==============================


def api_get_quotes():
    try:
        r = requests.get(f"{API_BASE}/quotes", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Error fetching quotes:", e)
        return []


def api_get_quote(quote_id):
    try:
        r = requests.get(f"{API_BASE}/quotes/{quote_id}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Error fetching quote detail:", e)
        return None


def api_create_quote(payload):
    try:
        r = requests.post(f"{API_BASE}/quotes", json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Error creating quote:", e)
        return None


def api_update_quote(quote_id, payload):
    try:
        r = requests.put(f"{API_BASE}/quotes/{quote_id}", json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Error updating quote:", e)
        return None


# NOTE: This expects your FastAPI schema shaped roughly like:
# GET /quotes -> list[ { "id": int, "customer_name": str, "estimator": str, "total_price": float, "status": str, "created_at": str } ]
# GET /quotes/{id} -> { "id": int, "customer_id": int, "customer_name": str, "job_type": str, "estimator": str,
#                        "items": [ { "name": str, "type": "Part"|"Labor", "cost": float, "price": float, "qty": float } ] }
# POST /quotes & PUT /quotes/{id} -> accept similar payload and return the saved quote.


# ==============================
# LAYOUT
# ==============================

def build_navbar():
    return dbc.Navbar(
        dbc.Container(
            [
                html.Div(
                    [
                        html.I(className="bi bi-lightning-charge-fill me-2"),
                        html.Span("TradeOps Field", className="fw-bold"),
                    ],
                    className="navbar-brand d-flex align-items-center",
                ),
                html.Span("Tech View", className="text-light small"),
            ]
        ),
        color="dark",
        dark=True,
        sticky="top",
        className="shadow-sm",
    )


def build_quote_table():
    return dash_table.DataTable(
        id="tbl-quotes",
        columns=[
            {"name": "Quote #", "id": "id"},
            {"name": "Customer", "id": "customer_name"},
            {"name": "Estimator", "id": "estimator"},
            {"name": "Total", "id": "total_price"},
            {"name": "Status", "id": "status"},
        ],
        style_cell={"padding": "8px", "fontSize": 14},
        style_header={"fontWeight": "bold", "backgroundColor": "#f8f9fa"},
        style_as_list_view=True,
        row_selectable="single",
        selected_rows=[],
        page_size=10,
        id_more="tbl-quotes",
    )


app.layout = html.Div(
    [
        dcc.Store(id="store-cart", data=[]),
        dcc.Store(id="store-edit-mode", data={"mode": "new", "quote_id": None}),
        dcc.Store(id="store-quotes", data=[]),
        dcc.Interval(id="interval-init", interval=500, n_intervals=0, max_intervals=1),
        build_navbar(),
        dbc.Container(
            [
                html.Br(),
                dbc.Tabs(
                    id="tabs-main",
                    active_tab="tab-quotes",
                    children=[
                        dbc.Tab(label="Quotes", tab_id="tab-quotes", tab_class_name="fw-semibold"),
                        dbc.Tab(label="Builder", tab_id="tab-builder", tab_class_name="fw-semibold"),
                    ],
                ),
                html.Div(id="tab-content", className="mt-3"),
            ],
            fluid=True,
        ),
    ]
)


# ==============================
# TAB CONTENT
# ==============================

@app.callback(
    Output("tab-content", "children"),
    Input("tabs-main", "active_tab"),
)
def render_tab(active_tab):
    if active_tab == "tab-quotes":
        return dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.Span("💼 Quote History", className="fw-bold"),
                                        html.Span(
                                            id="lbl-quotes-count",
                                            className="ms-2 text-muted small",
                                        ),
                                    ]
                                ),
                                dbc.CardBody(
                                    [
                                        build_quote_table(),
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    "Refresh",
                                                    id="btn-refresh-quotes",
                                                    color="secondary",
                                                    size="sm",
                                                    className="me-2 mt-2",
                                                ),
                                                dbc.Button(
                                                    "Edit Selected in Builder",
                                                    id="btn-edit-selected",
                                                    color="primary",
                                                    size="sm",
                                                    className="mt-2",
                                                ),
                                            ],
                                            className="d-flex justify-content-between",
                                        ),
                                        html.Div(
                                            id="quotes-error",
                                            className="text-danger small mt-2",
                                        ),
                                    ]
                                ),
                            ],
                            className="shadow-sm",
                        )
                    ],
                    xs=12,
                    lg=12,
                ),
            ]
        )

    # Builder tab
    return dbc.Row(
        [
            # Left: Customer + Job
            dbc.Col(
                [
                    dbc.Card(
                        [
                            dbc.CardHeader("1. Customer & Job"),
                            dbc.CardBody(
                                [
                                    dbc.Label("Customer"),
                                    dcc.Dropdown(
                                        id="dd-customer",
                                        options=customer_options(),
                                        placeholder="Select customer...",
                                    ),
                                    dbc.Button(
                                        "Use Mock: Mrs. Jones",
                                        id="btn-use-mock-customer",
                                        size="sm",
                                        color="link",
                                        className="px-0 mt-1",
                                    ),
                                    html.Hr(),
                                    dbc.Label("Job Type"),
                                    dbc.RadioItems(
                                        id="rad-job-type",
                                        options=[
                                            {"label": "Service", "value": "Service"},
                                            {"label": "Install", "value": "Install"},
                                        ],
                                        inline=True,
                                    ),
                                    html.Br(),
                                    dbc.Label("Estimator"),
                                    dbc.Input(
                                        id="txt-estimator",
                                        placeholder="Tech / Estimator name",
                                    ),
                                ]
                            ),
                        ],
                        className="mb-3 shadow-sm",
                    )
                ],
                xs=12,
                lg=4,
            ),

            # Middle: Items
            dbc.Col(
                [
                    dbc.Card(
                        [
                            dbc.CardHeader("2. Items"),
                            dbc.CardBody(
                                [
                                    dbc.Tabs(
                                        [
                                            dbc.Tab(
                                                label="Parts",
                                                tab_id="tab-parts",
                                                children=[
                                                    html.Br(),
                                                    dcc.Dropdown(
                                                        id="dd-part",
                                                        options=part_options(),
                                                        placeholder="Search part / service...",
                                                    ),
                                                    dbc.Input(
                                                        id="num-part-qty",
                                                        type="number",
                                                        min=1,
                                                        value=1,
                                                        className="mt-2",
                                                        placeholder="Quantity",
                                                    ),
                                                    dbc.Button(
                                                        "Add Part",
                                                        id="btn-add-part",
                                                        color="secondary",
                                                        className="mt-2 w-100",
                                                    ),
                                                ],
                                            ),
                                            dbc.Tab(
                                                label="Labor",
                                                tab_id="tab-labor",
                                                children=[
                                                    html.Br(),
                                                    dcc.Dropdown(
                                                        id="dd-labor",
                                                        options=labor_options(),
                                                        placeholder="Select labor role...",
                                                    ),
                                                    dbc.Input(
                                                        id="num-labor-hrs",
                                                        type="number",
                                                        min=0.5,
                                                        step=0.5,
                                                        className="mt-2",
                                                        placeholder="Hours",
                                                    ),
                                                    dbc.Button(
                                                        "Add Labor",
                                                        id="btn-add-labor",
                                                        color="secondary",
                                                        className="mt-2 w-100",
                                                    ),
                                                ],
                                            ),
                                        ]
                                    )
                                ]
                            ),
                        ],
                        className="mb-3 shadow-sm",
                    )
                ],
                xs=12,
                lg=4,
            ),

            # Right: Summary
            dbc.Col(
                [
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    "3. Summary",
                                    html.Span(
                                        id="lbl-edit-mode",
                                        className="badge bg-info ms-2",
                                    ),
                                ]
                            ),
                            dbc.CardBody(
                                [
                                    html.Div(
                                        id="div-cart-list",
                                        style={
                                            "maxHeight": "240px",
                                            "overflowY": "auto",
                                            "border": "1px solid #eee",
                                            "borderRadius": "4px",
                                        },
                                        className="mb-2",
                                    ),
                                    html.Div(
                                        [
                                            html.Span("Total:", className="fw-semibold"),
                                            html.Span(
                                                id="lbl-cart-total",
                                                className="float-end fw-bold text-success",
                                            ),
                                        ],
                                        className="mb-2",
                                    ),
                                    dbc.Button(
                                        "Save Quote",
                                        id="btn-save-quote",
                                        color="success",
                                        className="w-100 mt-1",
                                        size="lg",
                                    ),
                                    html.Div(id="save-msg", className="mt-2"),
                                ]
                            ),
                        ],
                        className="mb-3 shadow-sm",
                    )
                ],
                xs=12,
                lg=4,
            ),
        ]
    )


# ==============================
# INITIAL LOAD: FETCH QUOTES
# ==============================

@app.callback(
    [Output("store-quotes", "data"), Output("lbl-quotes-count", "children"), Output("quotes-error", "children")],
    [Input("interval-init", "n_intervals"), Input("btn-refresh-quotes", "n_clicks")],
)
def init_or_refresh_quotes(n_init, n_refresh):
    trigger = ctx.triggered_id
    if trigger is None:
        raise dash.exceptions.PreventUpdate

    quotes = api_get_quotes()
    if not quotes:
        return [], "(0 quotes)", "No quotes found or API unavailable."

    label = f"({len(quotes)} quotes)"
    return quotes, label, ""


@app.callback(
    Output("tbl-quotes", "data"),
    Input("store-quotes", "data"),
)
def update_quotes_table(quotes):
    return quotes or []


# ==============================
# QUOTES TAB → LOAD INTO BUILDER
# ==============================

@app.callback(
    [Output("tabs-main", "active_tab"),
     Output("store-edit-mode", "data"),
     Output("store-cart", "data"),
     Output("dd-customer", "value"),
     Output("rad-job-type", "value"),
     Output("txt-estimator", "value"),
     Output("lbl-edit-mode", "children"),
     Output("save-msg", "children")],
    Input("btn-edit-selected", "n_clicks"),
    [State("tbl-quotes", "data"), State("tbl-quotes", "selected_rows")],
    prevent_initial_call=True,
)
def load_selected_into_builder(n_clicks, rows, selected_rows):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not selected_rows:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dbc.Alert("Select a quote first.", color="warning", className="mt-2")

    sel = rows[selected_rows[0]]
    quote_id = sel.get("id")
    detail = api_get_quote(quote_id)
    if not detail:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dbc.Alert("Unable to load quote details.", color="danger", className="mt-2")

    # Map into UI fields
    cust_id = detail.get("customer_id")
    job_type = detail.get("job_type")
    estimator = detail.get("estimator")
    items = detail.get("items", [])

    edit_mode = {"mode": "edit", "quote_id": quote_id}
    edit_label = f"Editing Quote #{quote_id}"

    return ("tab-builder", edit_mode, items, cust_id, job_type, estimator, edit_label, "")


# ==============================
# BUILDER: MOCK CUSTOMER OVERRIDE
# ==============================

@app.callback(
    Output("dd-customer", "value"),
    Input("btn-use-mock-customer", "n_clicks"),
    prevent_initial_call=True,
)
def use_mock_customer(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    # Just pick Mrs. Jones (id=1)
    return 1


# ==============================
# CART MANAGEMENT
# ==============================

@app.callback(
    [Output("store-cart", "data"),
     Output("div-cart-list", "children"),
     Output("lbl-cart-total", "children")],
    [Input("btn-add-part", "n_clicks"), Input("btn-add-labor", "n_clicks")],
    [State("store-cart", "data"),
     State("dd-part", "value"),
     State("num-part-qty", "value"),
     State("dd-labor", "value"),
     State("num-labor-hrs", "value")],
    prevent_initial_call=True,
)
def add_cart_items(n_part, n_labor, cart, part_val, part_qty, labor_val, labor_hrs):
    trigger = ctx.triggered_id
    cart = cart or []

    if trigger == "btn-add-part" and part_val:
        pid, name, cost, price = part_val.split("|")
        qty = float(part_qty or 1)
        cart.append(
            {
                "name": name,
                "type": "Part",
                "cost": float(cost),
                "price": float(price),
                "qty": qty,
            }
        )

    if trigger == "btn-add-labor" and labor_val:
        role, cost, rate = labor_val.split("|")
        hrs = float(labor_hrs or 0)
        if hrs > 0:
            cart.append(
                {
                    "name": f"Labor: {role}",
                    "type": "Labor",
                    "cost": float(cost),
                    "price": float(rate),
                    "qty": hrs,
                }
            )

    # Render list + total
    total = sum(item["price"] * item["qty"] for item in cart) if cart else 0
    list_children = []
    for item in cart:
        list_children.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(item["name"], className="fw-semibold"),
                            html.Span(
                                f"${item['price'] * item['qty']:.2f}",
                                className="float-end",
                            ),
                        ]
                    ),
                    html.Div(
                        f"{item['type']} — x{item['qty']}",
                        className="text-muted small",
                    ),
                ],
                className="border-bottom px-2 py-1",
            )
        )

    total_label = f"${total:,.2f}"
    return cart, list_children, total_label


# ==============================
# SAVE QUOTE (NEW OR EDIT)
# ==============================

@app.callback(
    [Output("save-msg", "children"),
     Output("store-quotes", "data"),
     Output("lbl-edit-mode", "children"),
     Output("store-edit-mode", "data")],
    Input("btn-save-quote", "n_clicks"),
    [State("dd-customer", "value"),
     State("rad-job-type", "value"),
     State("txt-estimator", "value"),
     State("store-cart", "data"),
     State("store-edit-mode", "data"),
     State("store-quotes", "data")],
    prevent_initial_call=True,
)
def save_quote(n_clicks, customer_id, job_type, estimator, cart, edit_mode, quotes):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    # Validation
    errors = []
    if not customer_id:
        errors.append("Select a customer.")
    if not job_type:
        errors.append("Select a job type.")
    if not estimator:
        errors.append("Enter an estimator/tech name.")
    if not cart:
        errors.append("Add at least one item.")

    if errors:
        return (
            dbc.Alert(
                html.Ul([html.Li(e) for e in errors]),
                color="danger",
                className="mt-2",
            ),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    total = sum(item["price"] * item["qty"] for item in (cart or []))

    # Find customer name from mock list
    cust_name = next((c["name"] for c in MOCK_CUSTOMERS if c["id"] == customer_id), "Unknown Customer")

    payload = {
        "customer_id": customer_id,
        "customer_name": cust_name,
        "job_type": job_type,
        "estimator": estimator,
        "total_price": total,
        "status": "Draft",
        "items": cart,
    }

    mode = (edit_mode or {}).get("mode", "new")
    quote_id = (edit_mode or {}).get("quote_id")

    if mode == "edit" and quote_id:
        saved = api_update_quote(quote_id, payload)
        if not saved:
            return (
                dbc.Alert("Error updating quote. Check API logs.", color="danger", className="mt-2"),
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )
        msg = f"Quote #{quote_id} updated."
        new_mode = {"mode": "edit", "quote_id": quote_id}
        edit_label = f"Editing Quote #{quote_id}"
    else:
        saved = api_create_quote(payload)
        if not saved or "id" not in saved:
            return (
                dbc.Alert("Error creating quote. Check API logs.", color="danger", className="mt-2"),
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )
        quote_id = saved["id"]
        msg = f"Quote #{quote_id} created."
        new_mode = {"mode": "edit", "quote_id": quote_id}
        edit_label = f"Editing Quote #{quote_id}"

    # Refresh quotes store (append or refetch)
    new_quotes = api_get_quotes()

    return (
        dbc.Alert(msg, color="success", className="mt-2"),
        new_quotes or quotes,
        edit_label,
        new_mode,
    )


if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8051)
