import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import tradeops_v3_db as db
from fpdf import FPDF
from datetime import datetime, timedelta
import re
import os

# FORCE DB INIT ON STARTUP
db.init_db()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.BOOTSTRAP],
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]
)
app.title = "TradeOps Field V7"
server = app.server

# =========================================================
# PDF ENGINE
# =========================================================
def generate_pdf(quote_id, customer_name, items, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 10, "TradeOps Services", ln=True, align='C')

    pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, "123 Main St, Texas City, TX  |  (555) 555-0199", ln=True, align='C')
    pdf.cell(0, 8, "support@tradeops.com", ln=True, align='C')
    pdf.ln(5)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)

    date_str = datetime.now().strftime('%Y-%m-%d')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"Quote #: {quote_id}", ln=True)
    pdf.cell(0, 8, f"Customer: {customer_name}", ln=True)
    pdf.cell(0, 8, f"Date: {date_str}", ln=True)
    pdf.ln(5)

    # Table header
    pdf.set_font("Arial", 'B', 11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 8, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Price", 1, 1, 'R', 1)

    pdf.set_font("Arial", size=10)
    pdf.set_fill_color(250, 250, 250)
    fill = False
    for item in items:
        pdf.cell(100, 8, str(item['name'])[:55], 1, 0, 'L', fill)
        pdf.cell(30, 8, str(item['qty']), 1, 0, 'C', fill)
        pdf.cell(50, 8, f"${item['price']:.2f}", 1, 1, 'R', fill)
        fill = not fill

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 8, "Total Estimate:", 0, 0, 'R')
    pdf.cell(50, 8, f"${total:,.2f}", 0, 1, 'R')

    pdf.ln(15)
    pdf.set_font("Arial", 'I', 9)
    pdf.multi_cell(
        0,
        5,
        "This estimate is valid for 30 days from the date shown above. "
        "Pricing may change if additional work or materials are required.\n\n"
        "Thank you for choosing TradeOps."
    )

    clean_name = re.sub(r'[^a-zA-Z0-9]', '', customer_name or "Customer")
    filename = f"Quote_{clean_name}_{date_str}.pdf"
    pdf.output(filename)
    return filename

# =========================================================
# LAYOUTS
# =========================================================

# 1. FOLLOW-UP QUEUE TAB
followup_tab = dbc.Container(
    [
        html.Div(
            [
                html.H4("📞 Follow-Up Queue", className="mt-3 mb-1 text-primary"),
                html.Small("Stay on top of open quotes that still need a call-back.", className="text-muted"),
            ]
        ),
        html.Hr(),
        dbc.Button("↻ Refresh", id="btn-refresh-fup", color="outline-secondary", size="sm", className="mb-2"),
        dash_table.DataTable(
            id="fup-table",
            columns=[
                {"name": "Client", "id": "name"},
                {"name": "Phone", "id": "phone"},
                {"name": "Status", "id": "followup_status"},
                {"name": "Due", "id": "next_followup_date"},
            ],
            row_selectable='single',
            style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': 14},
            style_header={
                'fontWeight': 'bold',
                'backgroundColor': '#f1f3f4',
                'border': '1px solid #dee2e6'
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
            ],
            page_size=10
        ),
        dbc.Button(
            "Log Call / Update",
            id="btn-open-log",
            color="primary",
            className="mt-3 w-100",
            disabled=True,
        ),

        # Log Interaction Modal
        dbc.Modal(
            [
                dbc.ModalHeader("Log Interaction"),
                dbc.ModalBody(
                    [
                        dbc.Label("Outcome"),
                        dbc.Select(
                            id="log-outcome",
                            options=[
                                {"label": "Left Voicemail", "value": "Left VM"},
                                {"label": "Spoke - Not Ready", "value": "Needs Call"},
                                {"label": "Spoke - Sold!", "value": "Won"},
                                {"label": "Lost / Not Interested", "value": "Lost"},
                            ],
                            value="Needs Call",
                            className="mb-3",
                        ),
                        dbc.Label("Next Follow-Up Date"),
                        dcc.DatePickerSingle(
                            id="log-date",
                            date=(datetime.now() + timedelta(days=2)).date(),
                            display_format='YYYY-MM-DD',
                        ),
                        html.Br(),
                        html.Br(),
                        dbc.Button("Save & Update", id="btn-save-log", color="success", className="w-100 mb-2"),
                        html.Div(id="log-msg", className="small"),
                    ]
                ),
            ],
            id="modal-log",
            is_open=False,
            centered=True,
            backdrop=True,
        ),
    ],
    fluid=True,
)

# 2. HISTORY TAB
history_tab = dbc.Container(
    [
        html.Div(
            [
                html.H4("📂 Quote History", className="mt-3 mb-1 text-primary"),
                html.Small("Search and reuse previous estimates.", className="text-muted"),
            ]
        ),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Input(
                        id="hist-filter-input",
                        placeholder="Filter by Estimator Name…",
                        type="text",
                    ),
                    width=8,
                ),
                dbc.Col(
                    dbc.Button("Filter", id="btn-filter-hist", color="secondary", className="w-100"),
                    width=4,
                ),
            ],
            className="mb-2",
        ),
        dash_table.DataTable(
            id='history-table',
            columns=[
                {"name": "Client", "id": "name"},
                {"name": "Estimator", "id": "estimator"},
                {"name": "Total", "id": "total_price", "type": "numeric", "format": {"specifier": "$,.0f"}},
                {"name": "Status", "id": "status"},
                # keep quote_id hidden so callbacks can use it
                {"name": "Quote ID", "id": "quote_id", "hidden": True},
            ],
            style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': 14},
            style_header={
                'fontWeight': 'bold',
                'backgroundColor': '#f1f3f4',
                'border': '1px solid #dee2e6'
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
            ],
            row_selectable='single',
            page_size=10,
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "📝 Edit Quote",
                        id="btn-load-edit",
                        color="warning",
                        className="w-100",
                        disabled=True,
                    ),
                    width=6,
                ),
                dbc.Col(
                    dbc.Button(
                        "📄 Download PDF",
                        id="btn-dl-pdf",
                        color="info",
                        className="w-100",
                        disabled=True,
                    ),
                    width=6,
                ),
            ],
            className="mt-3",
        ),
        dcc.Download(id="download-pdf-component"),
    ],
    fluid=True,
)

# 3. QUOTE BUILDER TAB
quote_tab = dbc.Container(
    [
        dcc.Store(id="edit-mode-store", data={"mode": "new", "qid": None}),
        dbc.Row(
            [
                # CUSTOMER CARD
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("1. Customer", className="fw-bold"),
                            dbc.CardBody(
                                [
                                    dcc.Dropdown(
                                        id="cust-select",
                                        options=[],
                                        placeholder="Select an existing customer…",
                                    ),
                                    html.Br(),
                                    dbc.Button(
                                        "➕ New Customer",
                                        id="btn-new-cust",
                                        size="sm",
                                        color="outline-primary",
                                        className="w-100 mb-2",
                                    ),
                                    dbc.Modal(
                                        [
                                            dbc.ModalHeader("New Customer"),
                                            dbc.ModalBody(
                                                [
                                                    dbc.Input(
                                                        id="nc-name",
                                                        placeholder="Company / Name *",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="nc-street",
                                                        placeholder="Street",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="nc-city",
                                                        placeholder="City",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="nc-zip",
                                                        placeholder="Zip",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="nc-phone",
                                                        placeholder="Phone",
                                                        className="mb-2",
                                                    ),
                                                    dbc.Button(
                                                        "Save Customer",
                                                        id="btn-save-nc",
                                                        color="success",
                                                        className="w-100",
                                                    ),
                                                    html.Div(
                                                        id="nc-error",
                                                        className="small mt-2",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        id="nc-modal",
                                        is_open=False,
                                        centered=True,
                                    ),
                                    html.Hr(),
                                    dbc.Select(
                                        id="job-type",
                                        options=[
                                            {"label": "Service", "value": "Service"},
                                            {"label": "Install", "value": "Install"},
                                        ],
                                        placeholder="Job Type *",
                                        className="mb-2",
                                    ),
                                    dbc.Input(
                                        id="estimator",
                                        placeholder="Estimator Name *",
                                        className="mb-1",
                                    ),
                                    html.Small(
                                        "* Required fields",
                                        className="text-muted",
                                    ),
                                ]
                            ),
                        ],
                        className="h-100 shadow-sm",
                    ),
                    xs=12,
                    lg=4,
                    className="mb-3",
                ),

                # ITEMS CARD
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("2. Items", className="fw-bold"),
                            dbc.CardBody(
                                [
                                    dbc.Tabs(
                                        [
                                            dbc.Tab(
                                                label="Parts",
                                                children=[
                                                    html.Br(),
                                                    dcc.Dropdown(
                                                        id="part-select",
                                                        options=[],
                                                        placeholder="Search parts catalog…",
                                                    ),
                                                    dbc.Input(
                                                        id="part-qty",
                                                        type="number",
                                                        placeholder="Qty",
                                                        value=1,
                                                        className="mt-2",
                                                    ),
                                                    dbc.Button(
                                                        "Add Part",
                                                        id="btn-add-part",
                                                        color="secondary",
                                                        className="w-100 mt-2",
                                                    ),
                                                ],
                                            ),
                                            dbc.Tab(
                                                label="Labor",
                                                children=[
                                                    html.Br(),
                                                    dbc.Select(
                                                        id="labor-select",
                                                        options=[],
                                                        placeholder="Select role…",
                                                    ),
                                                    dbc.Input(
                                                        id="labor-hrs",
                                                        type="number",
                                                        placeholder="Hours",
                                                        className="mt-2",
                                                    ),
                                                    dbc.Button(
                                                        "Add Labor",
                                                        id="btn-add-labor",
                                                        color="secondary",
                                                        className="w-100 mt-2",
                                                    ),
                                                ],
                                            ),
                                        ]
                                    )
                                ]
                            ),
                        ],
                        className="h-100 shadow-sm",
                    ),
                    xs=12,
                    lg=4,
                    className="mb-3",
                ),

                # SUMMARY CARD
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("3. Summary", className="fw-bold"),
                            dbc.CardBody(
                                [
                                    html.Div(
                                        id="cart-list",
                                        style={"maxHeight": "240px", "overflowY": "auto"},
                                    ),
                                    html.Hr(),
                                    html.Div(
                                        [
                                            html.Span("Total", className="fw-semibold"),
                                            html.H3(
                                                id="cart-total",
                                                children="$0.00",
                                                className="text-end text-success mb-0",
                                            ),
                                        ]
                                    ),
                                    html.Br(),
                                    dbc.Button(
                                        "Finalize & Save Quote",
                                        id="btn-finalize",
                                        color="success",
                                        size="lg",
                                        className="w-100",
                                    ),
                                    html.Div(
                                        id="save-msg",
                                        className="mt-3",
                                    ),
                                ]
                            ),
                        ],
                        className="h-100 shadow-sm",
                    ),
                    xs=12,
                    lg=4,
                    className="mb-3",
                ),
            ]
        ),
    ],
    fluid=True,
)

# =========================================================
# APP LAYOUT
# =========================================================

app.layout = html.Div(
    style={"backgroundColor": "#f5f6f8", "minHeight": "100vh"},
    children=[
        dcc.Store(id="cart-store", data=[]),
        dbc.NavbarSimple(
            brand="TradeOps Field",
            brand_href="#",
            color="dark",
            dark=True,
            sticky="top",
        ),
        dbc.Container(
            [
                dbc.Tabs(
                    [
                        dbc.Tab(followup_tab, label="Follow-Up", tab_id="tab-fup"),
                        dbc.Tab(history_tab, label="History", tab_id="tab-hist"),
                        dbc.Tab(quote_tab, label="Builder", tab_id="tab-quote"),
                    ],
                    id="tabs",
                    active_tab="tab-fup",
                    className="mt-3",
                )
            ],
            fluid=True,
        ),
    ],
)

# =========================================================
# CALLBACKS / LOGIC
# =========================================================

# 1. LOAD DATA FOR BUILDER + HISTORY
@app.callback(
    [
        Output("cust-select", "options"),
        Output("part-select", "options"),
        Output("labor-select", "options"),
        Output("history-table", "data"),
    ],
    [
        Input("tabs", "active_tab"),
        Input("btn-filter-hist", "n_clicks"),
        Input("btn-refresh-hist", "n_clicks"),
    ],
    [State("hist-filter-input", "value")],
)
def load_data(tab, n_filter, n_refresh, filter_name):
    c_opts = [
        {"label": r["name"], "value": r["customer_id"]}
        for _, r in db.get_customers().iterrows()
    ]
    p_opts = [
        {
            "label": f"{r['name']} (${r['retail_price']})",
            "value": f"{r['part_id']}|{r['name']}|{r['cost']}|{r['retail_price']}",
        }
        for _, r in db.get_parts().iterrows()
    ]
    l_opts = [
        {
            "label": f"{r['role']} (${r['bill_rate']}/hr)",
            "value": f"{r['role']}|{r['base_cost']}|{r['bill_rate']}",
        }
        for _, r in db.get_labor().iterrows()
    ]

    hist_df = db.get_tech_history(estimator_name=filter_name)
    hist_data = hist_df.to_dict("records") if not hist_df.empty else []
    return c_opts, p_opts, l_opts, hist_data

# 2. FOLLOW-UP LOGIC
@app.callback(
    [
        Output("modal-log", "is_open"),
        Output("fup-table", "data"),
        Output("btn-open-log", "disabled"),
        Output("log-msg", "children"),
    ],
    [
        Input("btn-open-log", "n_clicks"),
        Input("btn-save-log", "n_clicks"),
        Input("tabs", "active_tab"),
        Input("btn-refresh-fup", "n_clicks"),
        Input("fup-table", "selected_rows"),
    ],
    [
        State("modal-log", "is_open"),
        State("fup-table", "data"),
        State("log-outcome", "value"),
        State("log-date", "date"),
    ],
)
def handle_followup(
    n_open,
    n_save,
    tab,
    n_refresh,
    selected,
    is_open,
    table_data,
    outcome,
    next_date,
):
    trigger = ctx.triggered_id
    selected = selected or []

    btn_disabled = False if selected else True
    msg = dash.no_update

    # load queue when tab changes or refresh clicked
    if trigger in ["tabs", "btn-refresh-fup"]:
        data = db.get_followup_queue().to_dict("records")
        return False, data, True, ""

    # row selection toggles button
    if trigger == "fup-table":
        return is_open, dash.no_update, btn_disabled, ""

    # open log modal
    if trigger == "btn-open-log":
        if not selected:
            return is_open, dash.no_update, btn_disabled, ""
        return True, dash.no_update, btn_disabled, ""

    # save log
    if trigger == "btn-save-log":
        if not selected:
            msg = dbc.Alert("Select a quote before logging.", color="danger", fade=True, is_open=True)
            return is_open, dash.no_update, btn_disabled, msg
        if not next_date:
            msg = dbc.Alert("Next follow-up date is required.", color="danger", fade=True, is_open=True)
            return is_open, dash.no_update, btn_disabled, msg

        row = table_data[selected[0]]
        db.log_interaction(row["quote_id"], outcome, next_date)
        data = db.get_followup_queue().to_dict("records")
        msg = dbc.Alert("Follow-up updated.", color="success", fade=True, is_open=True)
        return False, data, True, msg

    # default
    return is_open, dash.no_update, btn_disabled, msg

# 3. HISTORY ACTIONS (EDIT / PDF)
@app.callback(
    [
        Output("tabs", "active_tab", allow_duplicate=True),
        Output("cust-select", "value", allow_duplicate=True),
        Output("job-type", "value"),
        Output("estimator", "value"),
        Output("cart-store", "data", allow_duplicate=True),
        Output("edit-mode-store", "data"),
        Output("download-pdf-component", "data"),
        Output("btn-load-edit", "disabled"),
        Output("btn-dl-pdf", "disabled"),
    ],
    [
        Input("btn-load-edit", "n_clicks"),
        Input("btn-dl-pdf", "n_clicks"),
        Input("history-table", "selected_rows"),
    ],
    [State("history-table", "data")],
    prevent_initial_call=True,
)
def handle_history_actions(btn_edit, btn_pdf, selected, data):
    trigger = ctx.triggered_id
    selected = selected or []

    # No row selected: keep buttons disabled
    if not selected:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            True,
            True,
        )

    row = data[selected[0]]

    # Enable buttons when a row is selected (if we ever trigger from table)
    if trigger == "history-table":
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            False,
            False,
        )

    # LOAD INTO BUILDER
    if trigger == "btn-load-edit":
        header, items_df = db.get_quote_details(row["quote_id"])
        cart = (
            items_df[["item_name", "item_type", "unit_cost", "unit_price", "quantity"]]
            .rename(
                columns={
                    "item_name": "name",
                    "item_type": "type",
                    "unit_cost": "cost",
                    "unit_price": "price",
                    "quantity": "qty",
                }
            )
            .to_dict("records")
        )
        edit_data = {"mode": "edit", "qid": row["quote_id"]}
        return (
            "tab-quote",
            header["customer_id"],
            header["job_type"],
            header["estimator"],
            cart,
            edit_data,
            dash.no_update,
            False,
            False,
        )

    # DOWNLOAD PDF
    if trigger == "btn-dl-pdf":
        header, items_df = db.get_quote_details(row["quote_id"])
        items = (
            items_df[["item_name", "unit_price", "quantity"]]
            .rename(
                columns={
                    "item_name": "name",
                    "unit_price": "price",
                    "quantity": "qty",
                }
            )
            .to_dict("records")
        )
        pdf_file = generate_pdf(row["quote_id"], row["name"], items, header["total_price"])
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dcc.send_file(pdf_file),
            False,
            False,
        )

    # default
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        False,
        False,
    )

# 4. CUSTOMER CREATION & CART MANAGEMENT
@app.callback(
    [Output("nc-modal", "is_open"), Output("cust-select", "value"), Output("nc-error", "children")],
    [Input("btn-new-cust", "n_clicks"), Input("btn-save-nc", "n_clicks")],
    [
        State("nc-modal", "is_open"),
        State("nc-name", "value"),
        State("nc-street", "value"),
        State("nc-city", "value"),
        State("nc-zip", "value"),
        State("nc-phone", "value"),
    ],
)
def handle_cust(n1, n2, is_open, name, st, city, zipc, ph):
    trigger = ctx.triggered_id

    if trigger == "btn-new-cust":
        return True, dash.no_update, ""

    if trigger == "btn-save-nc":
        if not name:
            err = dbc.Alert("Customer name is required.", color="danger", fade=True, is_open=True)
            return True, dash.no_update, err
        # simple save; more validation if you want
        new_id = db.add_customer(name, st, city, "TX", zipc, ph)
        return False, new_id, dbc.Alert("Customer added.", color="success", fade=True, is_open=True)

    return is_open, dash.no_update, ""

@app.callback(
    [
        Output("cart-store", "data"),
        Output("cart-list", "children"),
        Output("cart-total", "children"),
    ],
    [
        Input("btn-add-part", "n_clicks"),
        Input("btn-add-labor", "n_clicks"),
        Input("edit-mode-store", "data"),
    ],
    [
        State("cart-store", "data"),
        State("part-select", "value"),
        State("part-qty", "value"),
        State("labor-select", "value"),
        State("labor-hrs", "value"),
    ],
)
def update_cart(b1, b2, edit_data, cart, p_val, p_qty, l_val, l_hrs):
    trigger = ctx.triggered_id
    cart = cart or []

    # when edit-mode-store changes, we don't touch cart here
    if trigger == "edit-mode-store":
        return dash.no_update, dash.no_update, dash.no_update

    if trigger == "btn-add-part" and p_val:
        try:
            pid, name, cost, price = p_val.split("|")
            qty = float(p_qty or 0)
            if qty <= 0:
                # ignore invalid qty silently for now (could show error if desired)
                pass
            else:
                cart.append(
                    {
                        "name": name,
                        "type": "Part",
                        "cost": float(cost),
                        "price": float(price),
                        "qty": qty,
                    }
                )
        except Exception:
            pass

    if trigger == "btn-add-labor" and l_val:
        try:
            role, cost, rate = l_val.split("|")
            hrs = float(l_hrs or 0)
            if hrs <= 0:
                pass
            else:
                cart.append(
                    {
                        "name": f"Labor: {role}",
                        "type": "Labor",
                        "cost": float(cost),
                        "price": float(rate),
                        "qty": hrs,
                    }
                )
        except Exception:
            pass

    items = [
        html.Div(
            [
                html.Span(f"{i['name']} (x{i['qty']})"),
                html.Span(f"${i['price'] * i['qty']:.2f}", className="float-end"),
            ],
            className="border-bottom py-1",
        )
        for i in cart
    ]
    total = sum(i["price"] * i["qty"] for i in cart) if cart else 0.0
    return cart, items, f"${total:,.2f}"

# 5. SAVE QUOTE (WITH VALIDATION + MESSAGES)
@app.callback(
    Output("save-msg", "children"),
    Input("btn-finalize", "n_clicks"),
    [
        State("cust-select", "value"),
        State("job-type", "value"),
        State("estimator", "value"),
        State("cart-store", "data"),
        State("edit-mode-store", "data"),
    ],
)
def save_quote(n, cust, jtype, est, cart, edit_mode):
    if not n:
        return ""

    cart = cart or []
    missing = []

    if not cust:
        missing.append("Customer")
    if not jtype:
        missing.append("Job Type")
    if not est:
        missing.append("Estimator")
    if not cart:
        missing.append("Items (add at least one Part or Labor line)")

    if missing:
        return dbc.Alert(
            f"Please complete all required fields before saving: {', '.join(missing)}.",
            color="danger",
            fade=True,
            is_open=True,
        )

    try:
        if edit_mode and edit_mode.get("mode") == "edit" and edit_mode.get("qid"):
            db.update_existing_quote(edit_mode["qid"], cust, jtype, est, cart)
            return dbc.Alert(
                "Quote updated successfully.",
                color="success",
                fade=True,
                is_open=True,
            )
        else:
            qid = db.save_new_quote(cust, jtype, est, cart)
            return dbc.Alert(
                f"Quote saved successfully. ID: {qid}",
                color="success",
                fade=True,
                is_open=True,
            )
    except Exception as e:
        return dbc.Alert(
            f"An error occurred while saving: {e}",
            color="danger",
            fade=True,
            is_open=True,
        )

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
