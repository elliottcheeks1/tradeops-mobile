import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import random
import io
import base64

# =========================================================
#   1. CONFIGURATION & THEME
# =========================================================
THEME = {
    "primary": "#2665EB",    # Royal Blue
    "secondary": "#6c757d",  # Grey
    "success": "#28a745",    # Green
    "bg_main": "#F4F7F6",    # Light Gray Background
    "bg_card": "#FFFFFF",    # White
    "text": "#2c3e50"        # Dark Slate
}

# Custom CSS for that "SaaS" look
custom_css = f"""
    body {{ background-color: {THEME['bg_main']}; font-family: 'Inter', sans-serif; }}
    
    /* Sidebar */
    .sidebar {{
        position: fixed; top: 0; left: 0; bottom: 0; width: 250px;
        padding: 2rem 1rem; background-color: #ffffff;
        box-shadow: 2px 0 10px rgba(0,0,0,0.05); z-index: 1000;
    }}
    
    /* Content Area */
    .content {{ margin-left: 260px; padding: 2rem; }}
    
    /* Cards */
    .saas-card {{
        background-color: #ffffff; border-radius: 12px; border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 1.5rem; margin-bottom: 1.5rem;
    }}
    
    /* Stepper */
    .stepper-item {{ text-align: center; position: relative; z-index: 1; }}
    .stepper-item.active .step-circle {{ background-color: {THEME['primary']}; color: white; border: none; }}
    .stepper-item.completed .step-circle {{ background-color: {THEME['success']}; color: white; border: none; }}
    .step-circle {{
        width: 30px; height: 30px; border-radius: 50%; border: 2px solid #ddd;
        background: #fff; display: flex; align-items: center; justify-content: center;
        margin: 0 auto 5px auto; font-weight: bold; font-size: 12px; color: #999;
    }}
    
    /* Nav Links */
    .nav-link {{ color: #555; font-weight: 500; padding: 10px 15px; border-radius: 8px; transition: 0.2s; }}
    .nav-link:hover, .nav-link.active {{ background-color: #EEF4FF; color: {THEME['primary']}; }}
"""

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP])
app.title = "TradeOps Field"
server = app.server

# =========================================================
#   2. MOCK DATA GENERATOR (Expanded for Charts)
# =========================================================
def generate_mock_data():
    techs = ["Elliott", "Sarah", "Mike", "John"]
    statuses = ["Draft", "Sent", "Approved", "Scheduled", "Invoiced", "Paid"]
    
    # Generate Quotes
    quotes = []
    for i in range(1001, 1050):
        created_date = date.today() - timedelta(days=random.randint(0, 60))
        status = random.choice(statuses)
        total = random.randint(200, 8500)
        cost = total * random.uniform(0.4, 0.6) # 40-60% cost
        
        quotes.append({
            "id": f"Q-{i}",
            "customer": f"Customer {i}",
            "status": status,
            "created_at": created_date.strftime("%Y-%m-%d"),
            "tech": random.choice(techs),
            "total": total,
            "cost": int(cost),
            "margin": int(total - cost),
            "items": [] # Simplified for aggregate data
        })
    return pd.DataFrame(quotes)

df_quotes = generate_mock_data()

# =========================================================
#   3. PDF GENERATOR
# =========================================================
def create_pdf(quote_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(38, 101, 235) # Brand Blue
    pdf.cell(0, 10, "TradeOps Field", ln=True)
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, f"Quote #{quote_data['id']} | Date: {date.today()}", ln=True)
    pdf.ln(10)
    
    # Line Items Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 10, "Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Price", 1, 1, 'R', 1)
    
    # Items
    pdf.set_font("Arial", "", 10)
    for item in quote_data.get('items', []):
        pdf.cell(100, 10, item['desc'], 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(60, 10, f"${item['price']}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 10, "TOTAL", 0, 0, 'R')
    pdf.cell(60, 10, f"${quote_data['total']:,.2f}", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# =========================================================
#   4. UI COMPONENTS
# =========================================================

def Sidebar():
    return html.Div([
        html.H3("TradeOps", className="fw-bold mb-5", style={"color": THEME['primary']}),
        dbc.Nav([
            dbc.NavLink([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="bi bi-calendar-week me-2"), "Schedule"], href="/schedule", active="exact"),
            dbc.NavLink([html.I(className="bi bi-file-earmark-text me-2"), "Quotes"], href="/quotes", active="exact"),
            dbc.NavLink([html.I(className="bi bi-gear me-2"), "Settings"], href="/settings", disabled=True),
        ], vertical=True, pills=True)
    ], className="sidebar")

def KPICard(title, value, subtext, icon, trend="up"):
    color = "success" if trend == "up" else "danger"
    icon_trend = "bi-arrow-up" if trend == "up" else "bi-arrow-down"
    
    return dbc.Col(html.Div([
        dbc.Row([
            dbc.Col([
                html.H6(title, className="text-muted text-uppercase small fw-bold"),
                html.H3(value, className="fw-bold mb-0"),
            ]),
            dbc.Col(html.Div(html.I(className=icon), style={
                "backgroundColor": "#EEF4FF", "color": THEME['primary'], 
                "width": "40px", "height": "40px", "borderRadius": "50%",
                "display": "flex", "alignItems": "center", "justifyContent": "center"
            }), width="auto")
        ], align="center"),
        html.Div([
            dbc.Badge([html.I(className=f"bi {icon_trend} me-1"), subtext], color=f"light-{color}", className=f"text-{color} p-1 mt-2"),
            html.Span(" vs last month", className="text-muted small ms-2")
        ])
    ], className="saas-card h-100"), md=3)

def JobStepper(status):
    steps = ["Draft", "Sent", "Approved", "Scheduled", "Invoiced", "Paid"]
    
    # Determine current index
    try:
        curr_idx = steps.index(status)
    except ValueError:
        curr_idx = 0
        
    step_cols = []
    for i, step in enumerate(steps):
        if i < curr_idx:
            cls = "stepper-item completed"
            icon = html.I(className="bi bi-check")
        elif i == curr_idx:
            cls = "stepper-item active"
            icon = str(i + 1)
        else:
            cls = "stepper-item"
            icon = str(i + 1)
            
        step_cols.append(dbc.Col(html.Div([
            html.Div(icon, className="step-circle"),
            html.Small(step, className="fw-bold")
        ], className=cls)))
        
    return html.Div(dbc.Row(step_cols, className="g-0"), className="mb-4 pt-3 pb-3 border-bottom")

# =========================================================
#   5. VIEW: DASHBOARD
# =========================================================
def DashboardView():
    # Calc logic
    total_rev = df_quotes['total'].sum()
    monthly_rev = df_quotes[df_quotes['created_at'] >= (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")]['total'].sum()
    open_est = len(df_quotes[df_quotes['status'].isin(['Draft', 'Sent'])])
    
    # Revenue Trend Chart
    df_trend = df_quotes.groupby('created_at')['total'].sum().reset_index()
    fig_trend = px.line(df_trend, x='created_at', y='total', markers=True)
    fig_trend.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20), height=300)
    fig_trend.update_traces(line_color=THEME['primary'], line_width=3)

    # Leaderboard
    df_tech = df_quotes.groupby('tech').agg({'total': 'sum', 'id': 'count'}).reset_index().sort_values('total', ascending=False)

    return html.Div([
        html.H2("Business Insights", className="fw-bold mb-4"),
        
        # Revenue Goal
        html.Div([
            html.Div([
                html.Span("Monthly Revenue Goal", className="fw-bold"),
                html.Span(f"${monthly_rev:,.0f} / $50,000", className="float-end text-muted")
            ], className="mb-2"),
            dbc.Progress([
                dbc.Progress(value=(monthly_rev/50000)*100, color="primary", bar=True),
            ], style={"height": "12px", "backgroundColor": "#e9ecef", "borderRadius": "6px"})
        ], className="saas-card"),
        
        # KPI Row
        dbc.Row([
            KPICard("Revenue MTD", f"${monthly_rev:,.0f}", "12%", "bi-currency-dollar"),
            KPICard("Open Estimates", str(open_est), "5%", "bi-file-earmark-text"),
            KPICard("Scheduled Today", "8", "2", "bi-calendar-check"),
            KPICard("Avg Job Size", f"${int(df_quotes['total'].mean()):,}", "8%", "bi-pie-chart"),
        ], className="mb-4"),
        
        dbc.Row([
            # Chart
            dbc.Col(html.Div([
                html.H5("Revenue Trend", className="fw-bold mb-3"),
                dcc.Graph(figure=fig_trend, config={'displayModeBar': False})
            ], className="saas-card h-100"), md=8),
            
            # Leaderboard
            dbc.Col(html.Div([
                html.H5("Top Technicians", className="fw-bold mb-3"),
                dash_table.DataTable(
                    data=df_tech.to_dict('records'),
                    columns=[{"name": "Tech", "id": "tech"}, {"name": "Rev", "id": "total", "format": {"specifier": "$,.0f"}}],
                    style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': 'Inter'},
                    style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa', 'border': 'none'},
                    style_data={'borderBottom': '1px solid #f0f0f0'}
                )
            ], className="saas-card h-100"), md=4),
        ])
    ])

# =========================================================
#   6. VIEW: QUOTE BUILDER (Split Screen)
# =========================================================
def QuoteBuilderView():
    return html.Div([
        dcc.Store(id="quote-state", data={"status": "Draft", "items": [], "total": 0, "id": "Q-NEW"}),
        dcc.Download(id="download-pdf"),
        
        dbc.Row([
            dbc.Col(html.H2("Quote Builder", className="fw-bold"), width=8),
            dbc.Col(html.Div(id="stepper-container"), width=12)
        ]),
        
        dbc.Row([
            # LEFT COLUMN: Customer & Actions
            dbc.Col([
                html.Div([
                    html.H5("Customer Details", className="fw-bold mb-3"),
                    dbc.Select(
                        id="cust-select",
                        options=[{"label": f"Customer {i}", "value": f"C-{i}"} for i in range(1, 6)],
                        placeholder="Select a customer...",
                        className="mb-3"
                    ),
                    html.Div([
                        html.P([html.I(className="bi bi-geo-alt me-2 text-primary"), "123 Maple Ave, Austin TX"]),
                        html.P([html.I(className="bi bi-envelope me-2 text-primary"), "client@email.com"]),
                        html.P([html.I(className="bi bi-telephone me-2 text-primary"), "(555) 123-4567"]),
                    ], className="bg-light p-3 rounded mb-4"),
                    
                    html.Hr(),
                    
                    html.H5("Actions", className="fw-bold mb-3"),
                    html.Div(id="action-buttons")
                    
                ], className="saas-card h-100")
            ], md=4),
            
            # RIGHT COLUMN: Cart
            dbc.Col([
                html.Div([
                    html.H5("Line Items", className="fw-bold mb-3"),
                    
                    # Add Item Row
                    dbc.Row([
                        dbc.Col(dbc.Input(id="new-item-desc", placeholder="Description (e.g., Service Call)"), md=6),
                        dbc.Col(dbc.Input(id="new-item-qty", type="number", value=1), md=2),
                        dbc.Col(dbc.Input(id="new-item-price", type="number", placeholder="Price"), md=3),
                        dbc.Col(dbc.Button(html.I(className="bi bi-plus"), id="btn-add-item", color="primary"), md=1),
                    ], className="mb-3 g-2"),
                    
                    # Items Table
                    html.Div(id="cart-items-container", style={"minHeight": "200px"}),
                    
                    html.Hr(),
                    
                    # Totals
                    dbc.Row([
                        dbc.Col(html.H4("Total Estimate", className="text-muted"), width=6),
                        dbc.Col(html.H2(id="cart-total-display", className="fw-bold text-end", style={"color": THEME['success']}), width=6),
                    ]),
                    dbc.Row([
                         dbc.Col(html.Small(id="margin-display", className="text-muted float-end"))
                    ])
                    
                ], className="saas-card h-100")
            ], md=8),
        ])
    ])

# =========================================================
#   7. VIEW: SMART SCHEDULER
# =========================================================
def ScheduleView():
    # Filter for 'Scheduled' jobs from mock data
    df_sched = df_quotes[df_quotes['status'] == 'Scheduled'].head(10)
    
    return html.Div([
        html.H2("Dispatch Board", className="fw-bold mb-4"),
        
        dbc.Row([
            # Dispatch List
            dbc.Col([
                html.Div([
                    dbc.Row([
                        dbc.Col(html.H5("Upcoming Jobs", className="fw-bold"), width=8),
                        dbc.Col(dbc.Button("Map View", color="outline-primary", size="sm", className="float-end"), width=4)
                    ], className="mb-3"),
                    
                    html.Div([
                        dbc.Card([
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.H6(row['customer'], className="fw-bold mb-0"),
                                        html.Small(f"ID: {row['id']} • {row['created_at']}", className="text-muted")
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Badge(row['tech'], color="info", className="me-2"),
                                        html.Small(f"${row['total']}", className="fw-bold")
                                    ], width=6, className="text-end")
                                ])
                            ])
                        ], className="mb-2 shadow-sm border-0") for i, row in df_sched.iterrows()
                    ])
                    
                ], className="saas-card")
            ], md=4),
            
            # Gantt / Timeline placeholder (Plotly)
            dbc.Col([
                html.Div([
                    html.H5("Technician Schedule", className="fw-bold mb-3"),
                    dcc.Graph(
                        figure=px.timeline(
                            df_sched, x_start="created_at", x_end="created_at", y="tech", color="tech",
                            title="Daily View"
                        ).update_layout(height=400, template="plotly_white"),
                        config={'displayModeBar': False}
                    )
                ], className="saas-card")
            ], md=8)
        ])
    ])

# =========================================================
#   8. MAIN LAYOUT
# =========================================================
app.layout = html.Div([
    dcc.Location(id="url"),
    html.Style(custom_css),
    Sidebar(),
    html.Div(id="page-content", className="content")
])

# =========================================================
#   9. CALLBACKS
# =========================================================

# Routing
@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname):
    if pathname == "/" or pathname == "/dashboard":
        return DashboardView()
    elif pathname == "/quotes":
        return QuoteBuilderView()
    elif pathname == "/schedule":
        return ScheduleView()
    return DashboardView()

# Quote Logic (Add Item, Update State, Generate PDF)
@app.callback(
    [Output("quote-state", "data"),
     Output("cart-items-container", "children"),
     Output("cart-total-display", "children"),
     Output("margin-display", "children"),
     Output("stepper-container", "children"),
     Output("action-buttons", "children"),
     Output("download-pdf", "data")],
    [Input("btn-add-item", "n_clicks"),
     Input({"type": "action-btn", "index": dash.ALL}, "n_clicks")],
    [State("new-item-desc", "value"),
     State("new-item-qty", "value"),
     State("new-item-price", "value"),
     State("quote-state", "data")]
)
def manage_quote(n_add, n_action, desc, qty, price, state):
    ctx_id = ctx.triggered_id
    
    # 1. Handle Add Item
    if ctx_id == "btn-add-item" and desc and price:
        new_item = {"desc": desc, "qty": float(qty or 1), "price": float(price)}
        state["items"].append(new_item)
        
    # 2. Handle Workflow Transitions
    pdf_download = None
    if isinstance(ctx_id, dict) and ctx_id.get("type") == "action-btn":
        action = ctx_id['index']
        if action == "send":
            state['status'] = "Sent"
            # Trigger PDF
            pdf_bytes = create_pdf(state)
            pdf_download = dcc.send_bytes(pdf_bytes, f"Quote_{state['id']}.pdf")
            
        elif action == "approve": state['status'] = "Approved"
        elif action == "schedule": state['status'] = "Scheduled"
        elif action == "complete": state['status'] = "Paid"

    # 3. Recalc Totals
    total = sum(i['qty'] * i['price'] for i in state['items'])
    state['total'] = total
    margin = total * 0.55 # Mock margin logic
    
    # 4. Render Cart HTML
    cart_html = [
        dbc.Row([
            dbc.Col(html.Span(i['desc']), width=6),
            dbc.Col(html.Span(f"x{i['qty']}"), width=2),
            dbc.Col(html.Span(f"${i['price'] * i['qty']:.2f}", className="fw-bold"), width=4),
        ], className="border-bottom py-2") for i in state['items']
    ]
    
    # 5. Render Actions based on State
    status = state['status']
    btn_style = {"width": "100%", "marginBottom": "10px"}
    
    if status == "Draft":
        buttons = [dbc.Button("Send to Customer (PDF)", id={"type": "action-btn", "index": "send"}, color="primary", style=btn_style)]
    elif status == "Sent":
        buttons = [
            dbc.Button("Mark Approved", id={"type": "action-btn", "index": "approve"}, color="success", style=btn_style),
            dbc.Button("Mark Lost", id={"type": "action-btn", "index": "lost"}, color="danger", outline=True, style=btn_style)
        ]
    elif status == "Approved":
        buttons = [dbc.Button("Schedule Job", id={"type": "action-btn", "index": "schedule"}, color="warning", style=btn_style)]
    elif status == "Scheduled":
        buttons = [dbc.Button("Complete & Invoice", id={"type": "action-btn", "index": "complete"}, color="success", style=btn_style)]
    else:
        buttons = [dbc.Button("Job Closed", disabled=True, color="secondary", style=btn_style)]

    return (state, cart_html, f"${total:,.2f}", f"Est. Margin: ${margin:,.2f}", 
            JobStepper(status), buttons, pdf_download)

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
