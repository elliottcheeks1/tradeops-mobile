# frontend_app.py
"""
Dash UI for TradeOps.

- Polished desktop dashboard + quote editor
- Uses mock data by default
- Tries to sync with FastAPI /quotes endpoints if available
"""

import os
from datetime import datetime

import dash
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import requests

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
# If API_BASE_URL is set (e.g. http://localhost:8000), we use it.
# In Render, API and Dash share the same origin, so "" means "same host".
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


# -------------------------------------------------------------------
# Mock data (used if API not reachable)
# -------------------------------------------------------------------
MOCK_QUOTES = [
    {
        "id": 1,
        "customer_name": "Kevin Parker",
        "status": "New Lead",
        "source": "Google Ads",
        "job_type": "HVAC Tune-up",
        "job_address": "123 Maple St",
        "created_at": "2025-12-20T09:15:00",
        "total_price": 356.00,
    },
    {
        "id": 2,
        "customer_name": "Johnathan Riley",
        "status": "First Contact",
        "source": "Web Form",
        "job_type": "16 SEER AC Install",
        "job_address": "456 Oak Ave",
        "created_at": "2025-12-20T10:30:00",
        "total_price": 8200.00,
    },
    {
        "id": 3,
        "customer_name": "High Point Creamery",
        "status": "Estimate Sent",
        "source": "Referral",
        "job_type": "Panel Upgrade 200A",
        "job_address": "18 Industrial Way",
        "created_at": "2025-12-19T14:45:00",
        "total_price": 5800.00,
    },
]


def as_df(quotes):
    if not quotes:
        return pd.DataFrame(MOCK_QUOTES)
    return pd.DataFrame(quotes)


# -------------------------------------------------------------------
# API helpers (safe: fall back to mock data)
# -------------------------------------------------------------------
def fetch_quotes():
    """Try to load from /quotes; on error use mock."""
    try:
        resp = requests.get(api_url("/quotes"), timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    return MOCK_QUOTES.copy()


def save_quote_api(quote):
    """
    Try to POST or PUT quote to API.
    If anything fails, just return the same quote (UI will still update).
    """
    try:
        quote_id = quote.get("id")
        payload = quote.copy()
        # created_at formatting
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = payload["created_at"].isoformat()

        if quote_id:
            resp = requests.put(api_url(f"/quotes/{quote_id}"), json=payload, timeout=5)
        else:
            resp = requests.post(api_url("/quotes"), json=payload, timeout=5)

        if resp.status_code in (200, 201):
            return resp.json()
    except Exception:
        pass
    return quote


# -------------------------------------------------------------------
# Dash app
# -------------------------------------------------------------------
external_stylesheets = [dbc.themes.BOOTSTRAP]

dash_app: Dash = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    requests_pathname_prefix="/app/",  # because we mount at /app
)

# Alias so FastAPI can import it
app = dash_app

# -------------------------------------------------------------------
# Layout components
# -------------------------------------------------------------------
def kpi_card(title, value, sublabel=None, pill=None, id=None):
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(title, className="text-muted small mb-1"),
                    html.Div(
                        value,
                        id=id,
                        className="h4 mb-0 fw-semibold",
                    ),
                    html.Div(
                        [
                            html.Span(
                                pill or "",
                                className="badge bg-success-subtle text-success me-2",
                            ),
                            html.Span(
                                sublabel or "",
                                className="text-muted small",
                            ),
                        ],
                        className="mt-1",
                    ),
                ]
            )
        ],
        className="shadow-sm h-100",
    )


def quote_editor_form():
    return dbc.Card(
        [
            dbc.CardHeader("Quote details", className="fw-semibold"),
            dbc.CardBody(
                [
                    dcc.Input(
                        id="quote-id",
                        type="hidden",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Input(
                                            id="customer-name",
                                            placeholder=" ",
                                            type="text",
                                        ),
                                        dbc.Label("Customer name"),
                                    ]
                                ),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Select(
                                            id="quote-status",
                                            options=[
                                                {
                                                    "label": "New Lead",
                                                    "value": "New Lead",
                                                },
                                                {
                                                    "label": "First Contact",
                                                    "value": "First Contact",
                                                },
                                                {
                                                    "label": "Estimate Sent",
                                                    "value": "Estimate Sent",
                                                },
                                                {
                                                    "label": "Approved",
                                                    "value": "Approved",
                                                },
                                                {
                                                    "label": "Lost",
                                                    "value": "Lost",
                                                },
                                            ],
                                        ),
                                        dbc.Label("Status"),
                                    ]
                                ),
                                md=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Input(
                                            id="job-type",
                                            placeholder=" ",
                                            type="text",
                                        ),
                                        dbc.Label("Job type"),
                                    ]
                                ),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Input(
                                            id="job-address",
                                            placeholder=" ",
                                            type="text",
                                        ),
                                        dbc.Label("Job address"),
                                    ]
                                ),
                                md=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Input(
                                            id="quote-source",
                                            placeholder=" ",
                                            type="text",
                                        ),
                                        dbc.Label("Source (e.g. Google Ads)"),
                                    ]
                                ),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.FormFloating(
                                    [
                                        dbc.Input(
                                            id="quote-total",
                                            placeholder=" ",
                                            type="number",
                                            step="0.01",
                                        ),
                                        dbc.Label("Quote total ($)"),
                                    ]
                                ),
                                md=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Button(
                        "Save quote",
                        id="save-quote-btn",
                        color="primary",
                        className="w-100",
                    ),
                    html.Div(
                        id="save-status",
                        className="text-success small mt-2",
                    ),
                ]
            ),
        ],
        className="shadow-sm h-100",
    )


dash_app.layout = dbc.Container(
    [
        dcc.Store(id="quotes-store"),  # holds list of quotes
        dcc.Interval(id="quotes-interval", interval=60 * 1000, n_intervals=0),
        html.Br(),
        # Top navbar / header
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H3("TradeOps Command Center", className="mb-0"),
                        html.Div(
                            "Today’s schedule, revenue, and open quotes at a glance.",
                            className="text-muted",
                        ),
                    ],
                    md=8,
                ),
                dbc.Col(
                    dbc.Button(
                        "New Quote",
                        id="new-quote-btn",
                        color="secondary",
                        className="float-end",
                    ),
                    md=4,
                ),
            ],
            align="center",
            className="mb-4",
        ),
        # KPI cards
        dbc.Row(
            [
                dbc.Col(
                    kpi_card(
                        "Open quotes",
                        "$0",
                        "Active opportunities",
                        pill="",
                        id="kpi-open-quotes",
                    ),
                    md=3,
                ),
                dbc.Col(
                    kpi_card(
                        "Avg quote size",
                        "$0",
                        "Average ticket",
                        pill="",
                        id="kpi-avg-quote",
                    ),
                    md=3,
                ),
                dbc.Col(
                    kpi_card(
                        "Quotes today",
                        "0",
                        "Created today",
                        pill="",
                        id="kpi-quotes-today",
                    ),
                    md=3,
                ),
                dbc.Col(
                    kpi_card(
                        "Win rate (mock)",
                        "42%",
                        "Last 30 days",
                        pill="",
                        id="kpi-win-rate",
                    ),
                    md=3,
                ),
            ],
            className="mb-4",
        ),
        # Main content: table + editor
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                html.Span(
                                                    "Pipeline",
                                                    className="fw-semibold",
                                                ),
                                                md=6,
                                            ),
                                            dbc.Col(
                                                dbc.InputGroup(
                                                    [
                                                        dbc.Input(
                                                            id="search-input",
                                                            placeholder="Search customers or jobs...",
                                                            type="text",
                                                        ),
                                                        dbc.Button(
                                                            "Search",
                                                            id="search-btn",
                                                            color="outline-secondary",
                                                        ),
                                                    ]
                                                ),
                                                md=6,
                                            ),
                                        ]
                                    )
                                ),
                                dbc.CardBody(
                                    [
                                        dash_table.DataTable(
                                            id="quotes-table",
                                            columns=[
                                                {
                                                    "name": "ID",
                                                    "id": "id",
                                                },
                                                {
                                                    "name": "Customer",
                                                    "id": "customer_name",
                                                },
                                                {
                                                    "name": "Status",
                                                    "id": "status",
                                                },
                                                {
                                                    "name": "Job",
                                                    "id": "job_type",
                                                },
                                                {
                                                    "name": "Source",
                                                    "id": "source",
                                                },
                                                {
                                                    "name": "Total ($)",
                                                    "id": "total_price",
                                                    "type": "numeric",
                                                    "format": dash_table.FormatTemplate.money(0),
                                                },
                                                {
                                                    "name": "Created",
                                                    "id": "created_at",
                                                },
                                            ],
                                            data=[],
                                            row_selectable="single",
                                            style_table={
                                                "height": "520px",
                                                "overflowY": "auto",
                                            },
                                            style_cell={
                                                "padding": "8px",
                                                "fontSize": 13,
                                            },
                                            style_header={
                                                "backgroundColor": "#f8f9fa",
                                                "fontWeight": "bold",
                                            },
                                            style_data_conditional=[
                                                {
                                                    "if": {
                                                        "filter_query": "{status} = 'New Lead'"
                                                    },
                                                    "backgroundColor": "#e8f2ff",
                                                },
                                                {
                                                    "if": {
                                                        "filter_query": "{status} = 'Approved'"
                                                    },
                                                    "backgroundColor": "#e6f4ea",
                                                },
                                            ],
                                        )
                                    ]
                                ),
                            ],
                            className="shadow-sm h-100",
                        )
                    ],
                    md=7,
                ),
                dbc.Col(quote_editor_form(), md=5),
            ],
            className="mb-4",
        ),
    ],
    fluid=True,
)


# -------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------
@dash_app.callback(
    Output("quotes-store", "data"),
    Input("quotes-interval", "n_intervals"),
    prevent_initial_call=False,
)
def load_quotes(_):
    """Load quotes from API or mock once per minute (and on first load)."""
    return fetch_quotes()


@dash_app.callback(
    [
        Output("quotes-table", "data"),
        Output("kpi-open-quotes", "children"),
        Output("kpi-avg-quote", "children"),
        Output("kpi-quotes-today", "children"),
    ],
    Input("quotes-store", "data"),
)
def update_table_and_kpis(quotes):
    df = as_df(quotes)

    # KPIs
    total_open = len(df)
    avg_size = df["total_price"].mean() if not df.empty else 0
    today = datetime.utcnow().date().isoformat()
    quotes_today = (
        df["created_at"]
        .astype(str)
        .str.slice(0, 10)
        .eq(today)
        .sum()
        if "created_at" in df.columns
        else 0
    )

    return (
        df.to_dict("records"),
        f"{total_open}",
        f"${avg_size:,.0f}",
        f"{quotes_today}",
    )


@dash_app.callback(
    [
        Output("quote-id", "value"),
        Output("customer-name", "value"),
        Output("quote-status", "value"),
        Output("job-type", "value"),
        Output("job-address", "value"),
        Output("quote-source", "value"),
        Output("quote-total", "value"),
        Output("save-status", "children"),
    ],
    [
        Input("quotes-table", "selected_rows"),
        Input("new-quote-btn", "n_clicks"),
    ],
    State("quotes-table", "data"),
    prevent_initial_call=True,
)
def populate_form(selected_rows, new_clicks, table_data):
    ctx = dash.callback_context

    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    # New quote
    if trigger == "new-quote-btn":
        return "", "", "New Lead", "", "", "", None, ""

    # Existing row selected
    if trigger == "quotes-table" and selected_rows:
        idx = selected_rows[0]
        row = table_data[idx]
        return (
            row.get("id"),
            row.get("customer_name"),
            row.get("status"),
            row.get("job_type"),
            row.get("job_address"),
            row.get("source"),
            row.get("total_price"),
            "",
        )

    raise dash.exceptions.PreventUpdate


@dash_app.callback(
    [
        Output("quotes-store", "data"),
        Output("save-status", "children"),
    ],
    Input("save-quote-btn", "n_clicks"),
    [
        State("quote-id", "value"),
        State("customer-name", "value"),
        State("quote-status", "value"),
        State("job-type", "value"),
        State("job-address", "value"),
        State("quote-source", "value"),
        State("quote-total", "value"),
        State("quotes-store", "data"),
    ],
    prevent_initial_call=True,
)
def save_quote(
    n_clicks,
    quote_id,
    customer_name,
    status,
    job_type,
    job_address,
    source,
    total_price,
    quotes_store,
):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    quotes = quotes_store or []

    # Build quote dict
    new_quote = {
        "id": quote_id,
        "customer_name": customer_name or "",
        "status": status or "New Lead",
        "job_type": job_type or "",
        "job_address": job_address or "",
        "source": source or "",
        "total_price": float(total_price or 0),
        "created_at": datetime.utcnow().isoformat(),
    }

    # Try to sync with API
    saved = save_quote_api(new_quote)

    # Merge back into local store
    if saved.get("id") is None:
        # If API didn't assign an id, fake one
        saved["id"] = max([q.get("id", 0) for q in quotes] + [0]) + 1

    # Update or append
    updated = False
    for i, q in enumerate(quotes):
        if q.get("id") == saved["id"]:
            quotes[i] = saved
            updated = True
            break
    if not updated:
        quotes.append(saved)

    return quotes, "Quote saved."


# For local debugging you *could* run this directly:
# if __name__ == "__main__":
#     dash_app.run_server(debug=True, host="0.0.0.0", port=8050)
