import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import random
import uuid

# =========================================================
#   1. MOCK DATABASE (Simulates Backend / Future API)
# =========================================================
class MockDB:
    def __init__(self):
        # Customers
        self.customers = [
            {"id": "C-1", "name": "Burger King #402", "address": "123 Whopper Ln", "city": "Austin", "email": "bk402@franchise.com"},
            {"id": "C-2", "name": "Marriott Downtown", "address": "400 Congress Ave", "city": "Austin", "email": "manager@marriott.com"},
            {"id": "C-3", "name": "Residential - John Doe", "address": "88 Maple St", "city": "Round Rock", "email": "john@gmail.com"},
        ]

        # Parts & labor catalog
        self.catalog = [
            {"id": "P-1", "name": "16 SEER Condenser (3 Ton)", "type": "Part", "cost": 1200, "price": 2800},
            {"id": "P-2", "name": "Evaporator Coil", "type": "Part", "cost": 450, "price": 950},
            {"id": "P-3", "name": "Smart Thermostat", "type": "Part", "cost": 120, "price": 350},
            {"id": "L-1", "name": "Labor - Master Tech", "type": "Labor", "cost": 60, "price": 185},
            {"id": "L-2", "name": "Labor - Apprentice", "type": "Labor", "cost": 25, "price": 85},
            {"id": "L-3", "name": "Trip Charge", "type": "Labor", "cost": 10, "price": 79},
        ]

        # Quotes
        self.quotes = []
        self._seed_quotes()

    # ---------- Seed some fake quotes ----------
    def _seed_quotes(self):
        statuses = ["Draft", "Sent", "Approved", "Scheduled", "Paid"]
        techs = ["Elliott", "Sarah", "Mike"]

        for i in range(1001, 1010):
            q_id = f"Q-{i}"
            cust = random.choice(self.customers)
            status = random.choice(statuses)

            items = []
            for _ in range(random.randint(1, 4)):
                item = random.choice(self.catalog)
                qty = random.randint(1, 3)
                items.append({
                    "id": str(uuid.uuid4()),
                    "desc": item["name"],
                    "qty": qty,
                    "price": item["price"],
                    "cost": item["cost"],
                    "type": item["type"],
                })

            total = sum(x["qty"] * x["price"] for x in items)
            created_at = (date.today() - timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d")

            self.quotes.append({
                "id": q_id,
                "customer_id": cust["id"],
                "customer_name": cust["name"],
                "address": cust["address"],
                "status": status,
                "created_at": created_at,
                "tech": random.choice(techs),
                "items": items,
                "total": total,
                "followup_date": (date.today() + timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d"),
                "job_date": None,
                "job_window": None,
                "notes": "",
            })

    # ---------- Helpers ----------
    def _next_quote_id(self):
        if not self.quotes:
            return "Q-1001"
        nums = []
        for q in self.quotes:
            try:
                nums.append(int(q["id"].split("-")[1]))
            except Exception:
                continue
        nxt = max(nums + [1000]) + 1
        return f"Q-{nxt}"

    # ---------- CRUD-ish API ----------
    def get_quotes_df(self):
        if not self.quotes:
            return pd.DataFrame(columns=[
                "id", "customer_name", "status", "created_at", "total",
                "followup_date", "job_date", "job_window", "tech"
            ])
        return pd.DataFrame(self.quotes)

    def get_quote(self, quote_id):
        return next((q for q in self.quotes if q["id"] == quote_id), None)

    def get_customers(self):
        return list(self.customers)

    def get_catalog(self):
        return list(self.catalog)

    def add_customer(self, name, address, city, email):
        new_id = f"C-{len(self.customers) + 1}"
        self.customers.append({
            "id": new_id,
            "name": name,
            "address": address or "",
            "city": city or "",
            "email": email or "",
        })
        return new_id

    def add_catalog_item(self, name, type_, cost, price):
        new_id = f"{type_[0]}-{len(self.catalog) + 1}"
        self.catalog.append({
            "id": new_id,
            "name": name,
            "type": type_,
            "cost": float(cost or 0),
            "price": float(price or 0),
        })

    def save_quote(self, state):
        """
        Upsert quote. Returns the normalized quote dict (with ID, totals, etc.).
        """
        data = state.copy()

        # Assign ID if new
        if not data.get("id") or data["id"] == "Q-NEW":
            data["id"] = self._next_quote_id()
            data.setdefault("created_at", date.today().strftime("%Y-%m-%d"))
        else:
            # keep existing created_at if present
            data.setdefault("created_at", date.today().strftime("%Y-%m-%d"))

        # Ensure mandatory fields
        data.setdefault("status", "Draft")
        data.setdefault("customer_name", "")
        data.setdefault("customer_id", None)
        data.setdefault("address", "")
        data.setdefault("tech", "Elliott")
        data.setdefault("items", [])
        data["total"] = sum(i["qty"] * i["price"] for i in data["items"])
        data.setdefault("followup_date", None)
        data.setdefault("job_date", None)
        data.setdefault("job_window", None)
        data.setdefault("notes", "")

        # Upsert into list
        idx = next((i for i, q in enumerate(self.quotes) if q["id"] == data["id"]), None)
        if idx is not None:
            self.quotes[idx] = data
        else:
            self.quotes.append(data)

        return data


db = MockDB()

# =========================================================
#   2. THEME & CUSTOM CSS
# =========================================================
THEME = {
    "primary": "#2665EB",
    "secondary": "#6c757d",
    "success": "#28a745",
    "bg_main": "#F4F7F6",
    "bg_card": "#FFFFFF",
    "text": "#2c3e50",
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

app.index_string = (
    """
<!DOCTYPE html>
<html>
    <head>
        {%metas%} <title>{%title%}</title> {%favicon%} {%css%}
        <style>"""
    + custom_css
    + """</style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%} {%scripts%} {%renderer%}</footer>
    </body>
</html>
"""
)

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
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, f"Quote #{quote_data['id']} | Date: {date.today()}", ln=True)
    pdf.cell(0, 8, f"Customer: {quote_data.get('customer_name', 'Valued Client')}", ln=True)
    if quote_data.get("address"):
        pdf.cell(0, 8, f"Service Address: {quote_data['address']}", ln=True)
    pdf.ln(8)

    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 8, "Description", 1, 0, "L", 1)
    pdf.cell(30, 8, "Qty", 1, 0, "C", 1)
    pdf.cell(60, 8, "Price", 1, 1, "R", 1)

    pdf.set_font("Arial", "", 10)
    for item in quote_data.get("items", []):
        pdf.cell(100, 8, item["desc"], 1)
        pdf.cell(30, 8, str(item["qty"]), 1, 0, "C")
        pdf.cell(60, 8, f"${item['price']*item['qty']:.2f}", 1, 1, "R")

    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 8, "TOTAL", 0, 0, "R")
    pdf.cell(60, 8, f"${quote_data['total']:,.2f}", 1, 1, "R")

    if quote_data.get("notes"):
        pdf.ln(6)
        pdf.set_font("Arial", "", 9)
        pdf.multi_cell(0, 5, f"Notes: {quote_data['notes']}")

    return pdf.output(dest="S").encode("latin-1")


# =========================================================
#   4. REUSABLE COMPONENTS
# =========================================================
def Sidebar():
    return html.Div(
        [
            html.H3("TradeOps", className="fw-bold mb-5", style={"color": THEME["primary"]}),
            dbc.Nav(
                [
                    dbc.NavLink(
                        [html.I(className="bi bi-speedometer2 me-2"), "Dashboard"],
                        href="/",
                        active="exact",
                    ),
                    dbc.NavLink(
                        [html.I(className="bi bi-calendar-week me-2"), "Schedule"],
                        href="/schedule",
                        active="exact",
                    ),
                    dbc.NavLink(
                        [html.I(className="bi bi-file-earmark-text me-2"), "Quotes"],
                        href="/quotes",
                        active="exact",
                    ),
                    dbc.NavLink(
                        [html.I(className="bi bi-gear me-2"), "Settings"],
                        href="/settings",
                        active="exact",
                    ),
                ],
                vertical=True,
                pills=True,
            ),
        ],
        className="sidebar",
    )


def JobStepper(status):
    steps = ["Draft", "Sent", "Approved", "Scheduled", "Paid"]
    try:
        curr_idx = steps.index(status)
    except Exception:
        curr_idx = 0

    cols = []
    for i, step in enumerate(steps):
        if i < curr_idx:
            cls, icon = "stepper-item completed", html.I(className="bi bi-check")
        elif i == curr_idx:
            cls, icon = "stepper-item active", str(i + 1)
        else:
            cls, icon = "stepper-item", str(i + 1)
        cols.append(
            dbc.Col(
                html.Div(
                    [html.Div(icon, className="step-circle"), html.Small(step, className="fw-bold")],
                    className=cls,
                )
            )
        )
    return html.Div(dbc.Row(cols, className="g-0"), className="mb-3 pt-2 pb-2 border-bottom")


# =========================================================
#   5. VIEWS
# =========================================================
def DashboardView():
    df = db.get_quotes_df()
    if df.empty:
        total_rev = 0
        monthly_rev = 0
        open_est = 0
        avg_job = 0
        win_rate = 0
    else:
        df["created_at"] = pd.to_datetime(df["created_at"])
        total_rev = df["total"].sum()
        cutoff = date.today() - timedelta(days=30)
        monthly_rev = df[df["created_at"].dt.date >= cutoff]["total"].sum()
        open_est = df[df["status"].isin(["Draft", "Sent"])]["id"].nunique()
        avg_job = df["total"].mean() if not df.empty else 0
        paid = df[df["status"] == "Paid"]["id"].nunique()
        attempts = df[df["status"].isin(["Sent", "Approved", "Scheduled", "Paid"])]["id"].nunique()
        win_rate = (paid / attempts * 100) if attempts else 0

    if df.empty:
        trend_fig = px.line()
    else:
        trend_df = df.groupby(df["created_at"].dt.date)["total"].sum().reset_index()
        trend_fig = px.line(trend_df, x="created_at", y="total", markers=True)
        trend_fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20), height=300)

    return html.Div(
        [
            html.H2("Business Insights", className="fw-bold mb-4"),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [html.H6("Revenue (Last 30 Days)"), html.H3(f"${monthly_rev:,.0f}", className="fw-bold")],
                            className="saas-card",
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        html.Div(
                            [html.H6("Open Estimates"), html.H3(open_est, className="fw-bold")],
                            className="saas-card",
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        html.Div(
                            [html.H6("Avg Job Size"), html.H3(f"${avg_job:,.0f}", className="fw-bold")],
                            className="saas-card",
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        html.Div(
                            [html.H6("Win Rate"), html.H3(f"{win_rate:,.0f}%", className="fw-bold")],
                            className="saas-card",
                        ),
                        md=3,
                    ),
                ],
                className="mb-4",
            ),
            html.Div(
                [html.H5("Revenue Trend", className="fw-bold"), dcc.Graph(figure=trend_fig)],
                className="saas-card",
            ),
        ]
    )


def QuotesView():
    quotes_df = db.get_quotes_df()
    pipeline_data = quotes_df[["id", "customer_name", "status", "created_at", "total"]].sort_values(
        "created_at", ascending=False
    )
    status_opts = [{"label": s, "value": s} for s in sorted(quotes_df["status"].dropna().unique())]

    return html.Div(
        [
            # Stores
            dcc.Store(
                id="quote-state",
                data={
                    "id": "Q-NEW",
                    "status": "Draft",
                    "items": [],
                    "total": 0,
                    "customer_name": "",
                    "customer_id": None,
                    "address": "",
                    "followup_date": None,
                    "job_date": None,
                    "job_window": None,
                    "notes": "",
                },
            ),
            dcc.Download(id="download-pdf"),
            html.H2("Quotes & Builder", className="fw-bold mb-4"),
            # Pipeline / list
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Dropdown(
                                    id="pipeline-status-filter",
                                    options=status_opts,
                                    multi=True,
                                    placeholder="Filter by status...",
                                ),
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Input(
                                    id="pipeline-search",
                                    placeholder="Search by customer...",
                                    type="text",
                                ),
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Button("New Quote", id="btn-new-quote", color="primary", className="w-100"),
                                md=2,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dash_table.DataTable(
                        id="quotes-table",
                        data=pipeline_data.to_dict("records"),
                        columns=[
                            {"name": "Quote #", "id": "id"},
                            {"name": "Customer", "id": "customer_name"},
                            {"name": "Status", "id": "status"},
                            {"name": "Created", "id": "created_at"},
                            {"name": "Total", "id": "total", "type": "numeric", "format": {"specifier": "$,.2f"}},
                        ],
                        style_header={"fontWeight": "bold", "backgroundColor": "#f8f9fa"},
                        style_cell={"textAlign": "left", "padding": "8px"},
                        page_size=8,
                        row_selectable="single",
                    ),
                    html.Small("Click a row to load it into the builder.", className="text-muted"),
                ],
                className="saas-card",
            ),
            # Builder
            dbc.Row(
                [
                    # LEFT: Customer / meta
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Customer & Job", className="fw-bold mb-3"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dcc.Dropdown(
                                                id="cust-select",
                                                options=[
                                                    {"label": c["name"], "value": c["id"]}
                                                    for c in db.get_customers()
                                                ],
                                                placeholder="Select Customer...",
                                            ),
                                            md=8,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                html.I(className="bi bi-person-plus"),
                                                id="btn-open-cust-modal",
                                                color="light",
                                                className="w-100",
                                            ),
                                            md=4,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                dbc.Label("Service Address"),
                                dbc.Input(id="job-address", placeholder="123 Main St", className="mb-3"),
                                dbc.Label("Follow-up Date"),
                                dcc.DatePickerSingle(
                                    id="followup-date",
                                    display_format="YYYY-MM-DD",
                                    className="mb-3",
                                ),
                                dbc.Label("Job Date & Time"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dcc.DatePickerSingle(
                                                id="job-date",
                                                display_format="YYYY-MM-DD",
                                            ),
                                            md=6,
                                        ),
                                        dbc.Col(
                                            dbc.Select(
                                                id="job-window",
                                                options=[
                                                    {"label": "8–10 AM", "value": "8-10"},
                                                    {"label": "10–12 PM", "value": "10-12"},
                                                    {"label": "1–3 PM", "value": "13-15"},
                                                    {"label": "3–5 PM", "value": "15-17"},
                                                ],
                                                placeholder="Window",
                                            ),
                                            md=6,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                dbc.Label("Internal Notes"),
                                dbc.Textarea(
                                    id="quote-notes",
                                    style={"height": "120px"},
                                    className="mb-3",
                                ),
                                html.Hr(),
                                html.H5("Actions", className="fw-bold mb-3"),
                                html.Div(id="action-buttons"),
                            ],
                            className="saas-card h-100",
                        ),
                        md=4,
                    ),
                    # RIGHT: Items & totals
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Line Items", className="fw-bold mb-3"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dcc.Dropdown(
                                                id="catalog-select",
                                                options=[
                                                    {"label": f"{i['name']} (${i['price']})", "value": i["id"]}
                                                    for i in db.get_catalog()
                                                ],
                                                placeholder="Search Parts/Labor...",
                                            ),
                                            md=7,
                                        ),
                                        dbc.Col(
                                            dbc.Input(
                                                id="item-qty",
                                                type="number",
                                                value=1,
                                                min=1,
                                            ),
                                            md=2,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Add",
                                                id="btn-add-item",
                                                color="primary",
                                                className="w-100",
                                            ),
                                            md=3,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                html.Div(id="cart-container", style={"minHeight": "200px"}),
                                html.Hr(),
                                dbc.Row(
                                    [
                                        dbc.Col(html.H4("Total", className="text-muted"), width=6),
                                        dbc.Col(
                                            html.H2(
                                                id="total-display",
                                                className="fw-bold text-end text-success",
                                            ),
                                            width=6,
                                        ),
                                    ]
                                ),
                            ],
                            className="saas-card h-100",
                        ),
                        md=8,
                    ),
                ]
            ),
            # New Customer Modal
            dbc.Modal(
                [
                    dbc.ModalHeader("Create New Customer"),
                    dbc.ModalBody(
                        [
                            dbc.Input(id="new-cust-name", placeholder="Name / Company", className="mb-2"),
                            dbc.Input(id="new-cust-addr", placeholder="Street Address", className="mb-2"),
                            dbc.Input(id="new-cust-city", placeholder="City", className="mb-2"),
                            dbc.Input(id="new-cust-email", placeholder="Email", className="mb-2"),
                        ]
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Create Customer", id="btn-create-cust", color="success")
                    ),
                ],
                id="modal-cust",
                is_open=False,
            ),
        ]
    )


def SettingsView():
    return html.Div(
        [
            html.H2("Settings & Catalog", className="fw-bold mb-4"),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Add Catalog Item", className="fw-bold mb-3"),
                                dbc.Input(id="cat-name", placeholder="Item Name", className="mb-2"),
                                dbc.Select(
                                    id="cat-type",
                                    options=[
                                        {"label": "Part", "value": "Part"},
                                        {"label": "Labor", "value": "Labor"},
                                    ],
                                    value="Part",
                                    className="mb-2",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Input(
                                                id="cat-cost",
                                                type="number",
                                                placeholder="Cost",
                                            ),
                                            width=6,
                                        ),
                                        dbc.Col(
                                            dbc.Input(
                                                id="cat-price",
                                                type="number",
                                                placeholder="Price",
                                            ),
                                            width=6,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                dbc.Button(
                                    "Add to Catalog",
                                    id="btn-add-catalog",
                                    color="primary",
                                    className="w-100",
                                ),
                                html.Div(id="cat-msg", className="mt-2 text-success"),
                            ],
                            className="saas-card",
                        ),
                        md=4,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Current Catalog", className="fw-bold mb-3"),
                                dash_table.DataTable(
                                    id="catalog-table",
                                    data=db.get_catalog(),
                                    columns=[
                                        {"name": "Name", "id": "name"},
                                        {"name": "Type", "id": "type"},
                                        {
                                            "name": "Price",
                                            "id": "price",
                                            "type": "numeric",
                                            "format": {"specifier": "$,.2f"},
                                        },
                                    ],
                                    style_header={
                                        "fontWeight": "bold",
                                        "backgroundColor": "#f8f9fa",
                                    },
                                    style_cell={"textAlign": "left", "padding": "10px"},
                                ),
                            ],
                            className="saas-card",
                        ),
                        md=8,
                    ),
                ]
            ),
        ]
    )


def ScheduleView():
    df = db.get_quotes_df()
    if df.empty:
        sched_df = pd.DataFrame(columns=["job_date", "tech", "customer_name"])
    else:
        sched_df = df[(df["status"] == "Scheduled") & df["job_date"].notna()].copy()
    if sched_df.empty:
        fig = px.timeline()
    else:
        sched_df["job_date"] = pd.to_datetime(sched_df["job_date"])
        fig = px.timeline(
            sched_df,
            x_start="job_date",
            x_end="job_date",
            y="tech",
            color="tech",
            hover_name="customer_name",
            title="Scheduled Jobs",
        )
        fig.update_layout(template="plotly_white")

    return html.Div(
        [
            html.H2("Smart Schedule", className="fw-bold mb-4"),
            html.Div([dcc.Graph(figure=fig)], className="saas-card"),
        ]
    )


# =========================================================
#   6. MAIN LAYOUT
# =========================================================
app.layout = html.Div(
    [
        dcc.Location(id="url"),
        Sidebar(),
        html.Div(id="page-content", className="content"),
    ]
)


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(path):
    if path == "/quotes":
        return QuotesView()
    if path == "/schedule":
        return ScheduleView()
    if path == "/settings":
        return SettingsView()
    return DashboardView()


# =========================================================
#   7. CALLBACKS – CUSTOMER / ADDRESS / CATALOG
# =========================================================
@app.callback(
    [Output("modal-cust", "is_open"), Output("cust-select", "options"), Output("cust-select", "value")],
    [Input("btn-open-cust-modal", "n_clicks"), Input("btn-create-cust", "n_clicks")],
    [
        State("modal-cust", "is_open"),
        State("new-cust-name", "value"),
        State("new-cust-addr", "value"),
        State("new-cust-city", "value"),
        State("new-cust-email", "value"),
    ],
)
def manage_customer(n_open, n_create, is_open, name, addr, city, email):
    trig = ctx.triggered_id
    if trig == "btn-open-cust-modal":
        return True, dash.no_update, dash.no_update
    if trig == "btn-create-cust" and name:
        new_id = db.add_customer(name, addr, city, email)
        opts = [{"label": c["name"], "value": c["id"]} for c in db.get_customers()]
        return False, opts, new_id
    opts = [{"label": c["name"], "value": c["id"]} for c in db.get_customers()]
    return is_open, opts, dash.no_update


@app.callback(Output("job-address", "value"), Input("cust-select", "value"))
def fill_address(cust_id):
    if not cust_id:
        return ""
    cust = next((c for c in db.get_customers() if c["id"] == cust_id), None)
    return cust["address"] if cust else ""


@app.callback(
    [Output("catalog-table", "data"), Output("cat-msg", "children"), Output("catalog-select", "options")],
    Input("btn-add-catalog", "n_clicks"),
    [State("cat-name", "value"), State("cat-type", "value"), State("cat-cost", "value"), State("cat-price", "value")],
)
def add_catalog_item(n, name, type_, cost, price):
    if n and name and price is not None:
        db.add_catalog_item(name, type_, cost, price)
        cat = db.get_catalog()
        opts = [{"label": f"{i['name']} (${i['price']})", "value": i["id"]} for i in cat]
        return cat, "Item added!", opts
    cat = db.get_catalog()
    opts = [{"label": f"{i['name']} (${i['price']})", "value": i["id"]} for i in cat]
    return cat, "", opts


# =========================================================
#   8. CALLBACKS – PIPELINE LIST
# =========================================================
@app.callback(
    Output("quotes-table", "data"),
    [Input("quote-state", "data"), Input("pipeline-status-filter", "value"), Input("pipeline-search", "value")],
)
def refresh_pipeline(state, statuses, search):
    df = db.get_quotes_df()
    if statuses:
        df = df[df["status"].isin(statuses)]
    if search:
        df = df[df["customer_name"].str.contains(search, case=False, na=False)]
    if df.empty:
        return []
    df = df.sort_values("created_at", ascending=False)
    return df[["id", "customer_name", "status", "created_at", "total"]].to_dict("records")


@app.callback(
    [
        Output("quote-state", "data"),
        Output("cust-select", "value"),
        Output("job-address", "value"),
        Output("followup-date", "date"),
        Output("job-date", "date"),
        Output("job-window", "value"),
        Output("quote-notes", "value"),
    ],
    [Input("quotes-table", "active_cell"), Input("btn-new-quote", "n_clicks")],
    State("quotes-table", "data"),
)
def load_quote(active_cell, n_new, table_data):
    trig = ctx.triggered_id
    # New Quote
    if trig == "btn-new-quote" or not active_cell:
        blank_state = {
            "id": "Q-NEW",
            "status": "Draft",
            "items": [],
            "total": 0,
            "customer_name": "",
            "customer_id": None,
            "address": "",
            "followup_date": None,
            "job_date": None,
            "job_window": None,
            "notes": "",
        }
        return blank_state, None, "", None, None, None, ""

    # Load from selected row
    row_idx = active_cell["row"]
    if row_idx is None or row_idx >= len(table_data):
        raise dash.exceptions.PreventUpdate
    quote_id = table_data[row_idx]["id"]
    q = db.get_quote(quote_id)
    if not q:
        raise dash.exceptions.PreventUpdate

    # Ensure minimal keys
    q.setdefault("followup_date", None)
    q.setdefault("job_date", None)
    q.setdefault("job_window", None)
    q.setdefault("notes", "")
    q.setdefault("customer_id", None)
    q.setdefault("address", "")

    return (
        q,
        q.get("customer_id"),
        q.get("address", ""),
        q.get("followup_date"),
        q.get("job_date"),
        q.get("job_window"),
        q.get("notes", ""),
    )


# =========================================================
#   9. CALLBACKS – QUOTE BUILDER (STATE + UI + PDF)
# =========================================================
@app.callback(
    [Output("quote-state", "data"), Output("download-pdf", "data")],
    [
        Input("btn-add-item", "n_clicks"),
        Input({"type": "action-btn", "index": ALL}, "n_clicks"),
        Input({"type": "delete-item", "index": ALL}, "n_clicks"),
    ],
    [
        State("catalog-select", "value"),
        State("item-qty", "value"),
        State("quote-state", "data"),
        State("cust-select", "value"),
        State("job-address", "value"),
        State("quote-notes", "value"),
        State("followup-date", "date"),
        State("job-date", "date"),
        State("job-window", "value"),
    ],
)
def update_quote(n_add, n_action, n_delete, cat_id, qty, state, cust_id, addr, notes, fup_date, job_date, job_window):
    trig = ctx.triggered_id
    if state is None:
        state = {
            "id": "Q-NEW",
            "status": "Draft",
            "items": [],
            "total": 0,
            "customer_name": "",
            "customer_id": None,
            "address": "",
            "followup_date": None,
            "job_date": None,
            "job_window": None,
            "notes": "",
        }

    # Keep meta in state
    state["customer_id"] = cust_id
    state["address"] = addr or ""
    state["notes"] = notes or ""
    state["followup_date"] = fup_date
    state["job_date"] = job_date
    state["job_window"] = job_window

    # Customer name
    if cust_id:
        c = next((x for x in db.get_customers() if x["id"] == cust_id), None)
        state["customer_name"] = c["name"] if c else "Unknown"
    else:
        state["customer_name"] = state.get("customer_name", "")

    pdf_bytes = None

    # --- Add line item ---
    if trig == "btn-add-item" and cat_id:
        item = next((i for i in db.get_catalog() if i["id"] == cat_id), None)
        if item:
            state.setdefault("items", [])
            state["items"].append(
                {
                    "id": str(uuid.uuid4()),
                    "desc": item["name"],
                    "qty": float(qty or 1),
                    "price": float(item["price"]),
                    "cost": float(item["cost"]),
                    "type": item["type"],
                }
            )

    # --- Delete line item ---
    if isinstance(trig, dict) and trig.get("type") == "delete-item":
        item_id = trig.get("index")
        state["items"] = [i for i in state.get("items", []) if i["id"] != item_id]

    # --- Status / lifecycle actions ---
    if isinstance(trig, dict) and trig.get("type") == "action-btn":
        action = trig.get("index")
        if action == "save":
            # Save without changing status
            state = db.save_quote(state)
        elif action == "send":
            state["status"] = "Sent"
            state = db.save_quote(state)
            pdf_bytes = create_pdf(state)
        elif action == "approve":
            state["status"] = "Approved"
            state = db.save_quote(state)
        elif action == "schedule":
            state["status"] = "Scheduled"
            state = db.save_quote(state)
        elif action == "complete":
            state["status"] = "Paid"
            state = db.save_quote(state)

    # Recalculate total in any case (local)
    state["total"] = sum(i["qty"] * i["price"] for i in state.get("items", []))

    if pdf_bytes:
        return state, dcc.send_bytes(pdf_bytes, f"Quote_{state['id']}.pdf")
    return state, None


@app.callback(
    [
        Output("cart-container", "children"),
        Output("total-display", "children"),
        Output("stepper-container", "children"),
        Output("action-buttons", "children"),
    ],
    Input("quote-state", "data"),
)
def render_quote_ui(state):
    if state is None:
        raise dash.exceptions.PreventUpdate

    items = state.get("items", [])
    total = state.get("total", 0)
    status = state.get("status", "Draft")

    # Render cart with delete buttons
    cart_rows = []
    for i in items:
        margin = (i["price"] - i["cost"]) * i["qty"]
        cart_rows.append(
            dbc.Row(
                [
                    dbc.Col(html.Small(i["desc"]), md=5),
                    dbc.Col(html.Small(f"x{i['qty']}"), md=2),
                    dbc.Col(html.Small(f"${i['price']*i['qty']:.2f}"), md=3, className="text-end"),
                    dbc.Col(
                        dbc.Button(
                            html.I(className="bi bi-trash"),
                            id={"type": "delete-item", "index": i["id"]},
                            color="link",
                            size="sm",
                        ),
                        md=2,
                        className="text-end",
                    ),
                    html.Div(
                        html.Small(f"Margin: ${margin:,.2f}", className="text-muted"),
                        className="mt-1",
                    ),
                ],
                className="border-bottom py-2",
            )
        )

    if not cart_rows:
        cart_rows = [html.P("No line items yet. Add something from the catalog.", className="text-muted")]

    total_text = f"${total:,.2f}"

    # Action buttons (always show Save + stage button)
    btn_props = {"style": {"width": "100%", "marginBottom": "8px"}}
    actions = [dbc.Button("💾 Save Draft", id={"type": "action-btn", "index": "save"}, color="secondary", **btn_props)]

    if status == "Draft":
        actions.append(
            dbc.Button("Send (PDF)", id={"type": "action-btn", "index": "send"}, color="primary", **btn_props)
        )
    elif status == "Sent":
        actions.append(
            dbc.Button("Approve", id={"type": "action-btn", "index": "approve"}, color="success", **btn_props)
        )
    elif status == "Approved":
        actions.append(
            dbc.Button("Schedule", id={"type": "action-btn", "index": "schedule"}, color="warning", **btn_props)
        )
    elif status == "Scheduled":
        actions.append(
            dbc.Button("Complete", id={"type": "action-btn", "index": "complete"}, color="success", **btn_props)
        )
    else:
        actions.append(
            dbc.Button("Closed", disabled=True, color="secondary", **btn_props)
        )

    return cart_rows, total_text, JobStepper(status), actions


# =========================================================
#   10. MAIN
# =========================================================
if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
