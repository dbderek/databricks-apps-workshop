import os
import time
from dash import Dash, html, dcc, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from databricks import sdk
import pandas as pd
from flask import request

# Initialize Databricks SDK
w = sdk.WorkspaceClient()

# Database configuration
PGHOST = os.environ.get("PGHOST", "")
PGDATABASE = os.environ.get("PGDATABASE", "")
PGUSER = os.environ.get("PGUSER", "")
PGPORT = os.environ.get("PGPORT", "5432")
PGSSLMODE = os.environ.get("PGSSLMODE", "require")
LAKEBASE_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "public")
LAKEBASE_TABLE = os.environ.get("LAKEBASE_TABLE", "support_tickets")

missing = [k for k, v in [("PGHOST", PGHOST), ("PGDATABASE", PGDATABASE), ("PGUSER", PGUSER)] if not v]

def db_url_without_password():
    return f"postgresql+psycopg://{PGUSER}:@{PGHOST}:{PGPORT}/{PGDATABASE}"

def get_engine():
    engine = create_engine(
        db_url_without_password(),
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={"sslmode": PGSSLMODE},
    )
    
    fallback_token_cache = {"value": None, "ts": 0}
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        try:
            user_email = request.headers.get('X-Forwarded-Email')
            user_token = request.headers.get('X-Forwarded-Access-Token')
            if user_email and user_token:
                cparams["user"] = user_email
                cparams["password"] = user_token
                return
        except RuntimeError:
            pass
        
        now = time.time()
        if fallback_token_cache["value"] is None or (now - fallback_token_cache["ts"]) > 900:
            try:
                fallback_token_cache["value"] = w.config.oauth_token().access_token
            except Exception:
                pass
            fallback_token_cache["ts"] = now
        cparams["password"] = fallback_token_cache["value"]
    
    return engine

def get_current_user():
    try:
        return request.headers.get('X-Forwarded-Email', 'Unknown')
    except RuntimeError:
        return 'Unknown'

def check_table_exists(engine):
    sql = "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = :schema AND table_name = :table)"
    with engine.begin() as conn:
        return conn.execute(text(sql), {"schema": LAKEBASE_SCHEMA, "table": LAKEBASE_TABLE}).scalar()

def get_all_users(engine):
    """Get distinct users from existing tickets for the assignee dropdown."""
    sql = f"SELECT DISTINCT assigned_to FROM {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} ORDER BY assigned_to"
    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql)).fetchall()
            return [row[0] for row in result]
    except Exception:
        return []

def get_tickets(engine, status_filter=None):
    sql = f"""
    SELECT id, title, description, customer_email, status, priority, assigned_to, created_at, updated_at
    FROM {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
    """
    params = {}
    if status_filter and status_filter != "all":
        sql += " WHERE status = :status"
        params["status"] = status_filter
    sql += " ORDER BY created_at DESC"
    
    with engine.begin() as conn:
        result = conn.execute(text(sql), params).mappings().all()
        return pd.DataFrame(result) if result else pd.DataFrame()

def create_ticket(engine, title, description, customer_email, priority, assigned_to):
    sql = f"""
    INSERT INTO {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} (title, description, customer_email, priority, status, assigned_to)
    VALUES (:title, :desc, :email, :priority, 'open', :assigned_to)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "title": title, "desc": description, "email": customer_email,
            "priority": priority, "assigned_to": assigned_to
        })

def update_ticket_status(engine, ticket_id, new_status):
    sql = f"UPDATE {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} SET status = :status, updated_at = now() WHERE id = :id"
    with engine.begin() as conn:
        conn.execute(text(sql), {"status": new_status, "id": ticket_id})

# Initialize
engine = None
table_exists = False
try:
    if not missing:
        engine = get_engine()
        table_exists = check_table_exists(engine)
except Exception as e:
    print(f"Database error: {e}")

# App setup
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Support Tickets"

# Custom CSS for modern styling
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * { font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif; }
            body { background: linear-gradient(135deg, #e8f4fc 0%, #f0f7ff 100%); min-height: 100vh; }
            .card-modern { background: white; border-radius: 16px; border: 1px solid #e5e7eb; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
            .card-modern:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
            .btn-primary { background: #2563eb; border-color: #2563eb; border-radius: 8px; font-weight: 500; }
            .btn-primary:hover { background: #1d4ed8; border-color: #1d4ed8; }
            .btn-outline-primary { border-radius: 8px; border-width: 2px; }
            .navbar { background: white !important; }
            .nav-link { font-weight: 500; color: #64748b !important; }
            .nav-link.active { color: #2563eb !important; }
            .badge { border-radius: 6px; font-weight: 500; padding: 6px 12px; }
            .form-control, .form-select { border-radius: 10px; border-color: #e5e7eb; padding: 10px 14px; }
            .form-control:focus, .form-select:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
            .ticket-row { background: white; border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; 
                          border: 1px solid #f1f5f9; transition: all 0.2s; }
            .ticket-row:hover { border-color: #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
            .column-header { font-size: 14px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
            .status-open { background: #fee2e2; color: #dc2626; }
            .status-in_progress { background: #fef3c7; color: #d97706; }
            .status-resolved { background: #d1fae5; color: #059669; }
            .status-closed { background: #e5e7eb; color: #6b7280; }
            .arrow-btn { width: 40px; height: 40px; border-radius: 10px; border: 2px solid #2563eb; 
                        color: #2563eb; display: flex; align-items: center; justify-content: center; }
            .arrow-btn:hover { background: #2563eb; color: white; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Styles
CARD_STYLE = {"borderRadius": "16px", "border": "none", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)"}
COLUMN_STYLE = {"backgroundColor": "white", "borderRadius": "16px", "padding": "20px", "minHeight": "400px",
                "border": "1px dashed #e2e8f0"}

status_colors = {"open": "danger", "in_progress": "warning", "resolved": "success", "closed": "secondary"}
priority_colors = {"low": "info", "medium": "warning", "high": "danger", "critical": "dark"}

def create_navbar(current_page):
    return dbc.Navbar(
        dbc.Container([
            html.Div([
                html.Span("*", style={"color": "#2563eb", "fontSize": "24px", "marginRight": "8px"}),
                dbc.NavbarBrand("Ticket Center", style={"color": "#2563eb", "fontWeight": "700", "fontSize": "20px"})
            ], className="d-flex align-items-center"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Submit Ticket", href="#", id="nav-submit", 
                    active=current_page == "submit", className="px-3")),
                dbc.NavItem(dbc.NavLink("My Tickets", href="#", id="nav-board", 
                    active=current_page == "board", className="px-3")),
            ], className="ms-auto"),
            html.Div(id="user-display", className="text-muted ms-3 small")
        ], fluid=True),
        color="white", className="mb-4", style={"boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "borderRadius": "0"}
    )

def create_submit_page():
    users = get_all_users(engine) if engine and table_exists else []
    user_options = [{"label": u, "value": u} for u in users]
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Submit a Ticket", className="mb-1", style={"fontWeight": "700", "color": "#1e293b"}),
                    html.P("Fill out the form below to create a new support request.", 
                          className="text-muted mb-4"),
                    
                    html.Div([
                        dbc.Label("Title", className="fw-semibold mb-2", style={"color": "#374151"}),
                        dbc.Input(id="ticket-title", placeholder="Brief summary of the issue", className="mb-4"),
                        
                        dbc.Label("Description", className="fw-semibold mb-2", style={"color": "#374151"}),
                        dbc.Textarea(id="ticket-description", placeholder="Detailed description of the issue...", 
                                   rows=4, className="mb-4"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Your Email", className="fw-semibold mb-2", style={"color": "#374151"}),
                                dbc.Input(id="ticket-email", type="email", placeholder="you@example.com", className="mb-4"),
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Priority", className="fw-semibold mb-2", style={"color": "#374151"}),
                                dbc.Select(id="ticket-priority", options=[
                                    {"label": "Low", "value": "low"},
                                    {"label": "Medium", "value": "medium"},
                                    {"label": "High", "value": "high"},
                                    {"label": "Critical", "value": "critical"}
                                ], value="medium", className="mb-4"),
                            ], md=6),
                        ]),
                        
                        dbc.Label("Assign To", className="fw-semibold mb-2", style={"color": "#374151"}),
                        dbc.Select(id="ticket-assignee", options=user_options,
                                  placeholder="Select team member...", className="mb-4"),
                        
                        dbc.Button("Submit Ticket", id="create-ticket-btn", color="primary", 
                                  className="w-100 py-2", style={"fontSize": "16px", "fontWeight": "600"}),
                        html.Div(id="create-ticket-output", className="mt-3")
                    ], className="card-modern p-4")
                ], className="py-4")
            ], lg=5, md=7, className="mx-auto")
        ], className="justify-content-center")
    ], fluid=True)

def create_ticket_card(row):
    priority_badge_colors = {"low": "#3b82f6", "medium": "#f59e0b", "high": "#ef4444", "critical": "#7c3aed"}
    return html.Div([
        html.Div([
            html.Span(f"#{row['id']}", style={"color": "#2563eb", "fontSize": "12px", "fontWeight": "600"}),
            html.Span(row['priority'].title(), 
                     style={"fontSize": "10px", "padding": "2px 6px", "borderRadius": "4px",
                            "background": priority_badge_colors.get(row['priority'], "#6b7280") + "20",
                            "color": priority_badge_colors.get(row['priority'], "#6b7280"),
                            "fontWeight": "600", "float": "right"})
        ], className="mb-2"),
        html.Div(row['title'], style={"fontWeight": "600", "color": "#1e293b", "fontSize": "14px", 
                                       "lineHeight": "1.3", "marginBottom": "8px"}),
        html.Div(row['customer_email'], style={"fontSize": "12px", "color": "#64748b", "marginBottom": "8px"}),
        html.Div([
            html.Span(row['created_at'].strftime('%b %d') if hasattr(row['created_at'], 'strftime') else "", 
                     style={"fontSize": "11px", "color": "#94a3b8"}),
            html.Button("Update", id={"type": "update-btn", "index": row['id']}, 
                       style={"fontSize": "12px", "padding": "4px 12px", "borderRadius": "6px",
                              "border": "1px solid #2563eb", "background": "white", "color": "#2563eb",
                              "cursor": "pointer", "fontWeight": "500", "float": "right"})
        ])
    ], style={"background": "white", "borderRadius": "12px", "padding": "14px", "marginBottom": "10px",
              "border": "1px solid #f1f5f9", "boxShadow": "0 1px 3px rgba(0,0,0,0.04)"})

def create_column(status, label, color):
    return html.Div([
        html.Div([
            html.Span(label, style={"fontWeight": "600", "color": "#1e293b", "fontSize": "14px"}),
            html.Span(id=f"count-{status}", style={"marginLeft": "8px", "padding": "2px 8px", 
                                                    "borderRadius": "10px", "fontSize": "12px",
                                                    "background": color + "20", "color": color, "fontWeight": "600"})
        ], style={"marginBottom": "16px"}),
        html.Div(id=f"column-{status}")
    ], style={"background": "#f8fafc", "borderRadius": "16px", "padding": "16px", "minHeight": "500px"})

def create_board_page():
    if not engine or not table_exists:
        return dbc.Container([
            dbc.Alert("Database not configured. Please run setup-lakebase.ipynb first.", color="warning")
        ])
    
    return dbc.Container([
        html.Div([
            html.H2("My Tickets", className="mb-1", style={"fontWeight": "700", "color": "#1e293b"}),
            html.P("View and manage tickets assigned to you.", className="text-muted mb-4"),
        ]),
        
        dbc.Row([
            dbc.Col([create_column("open", "Open", "#ef4444")], md=3),
            dbc.Col([create_column("in_progress", "In Progress", "#f59e0b")], md=3),
            dbc.Col([create_column("resolved", "Resolved", "#22c55e")], md=3),
            dbc.Col([create_column("closed", "Closed", "#6b7280")], md=3),
        ], className="g-3"),
        
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Update Status", style={"fontWeight": "600"})),
            dbc.ModalBody([
                html.Div(id="modal-ticket-info"),
                html.Hr(),
                dbc.Label("New Status", className="fw-semibold"),
                dbc.Select(id="modal-new-status", options=[
                    {"label": "Open", "value": "open"},
                    {"label": "In Progress", "value": "in_progress"},
                    {"label": "Resolved", "value": "resolved"},
                    {"label": "Closed", "value": "closed"}
                ], className="mb-3")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="close-modal-btn", outline=True, color="secondary", className="me-2"),
                dbc.Button("Update", id="update-ticket-btn", color="primary")
            ])
        ], id="update-modal", is_open=False, centered=True),
        
        html.Div(id="selected-ticket-id", style={"display": "none"}),
        html.Div(id="update-trigger", style={"display": "none"})
    ], fluid=True, className="py-4")

# Layout
app.layout = html.Div([
    dcc.Store(id="current-page", data="submit"),
    dcc.Store(id="refresh-trigger", data=0),
    html.Div(id="navbar-container"),
    html.Div(id="page-content"),
    dcc.Interval(id="refresh-interval", interval=30000, n_intervals=0)
])

# Callbacks
@callback(Output("navbar-container", "children"), Input("current-page", "data"))
def update_navbar(page):
    return create_navbar(page)

@callback(Output("user-display", "children"), Input("refresh-interval", "n_intervals"))
def update_user(n):
    user = get_current_user()
    return f"Logged in: {user}" if user != "Unknown" else ""

@callback(Output("current-page", "data"), Input("nav-submit", "n_clicks"), Input("nav-board", "n_clicks"),
          State("current-page", "data"), prevent_initial_call=True)
def navigate(submit_clicks, board_clicks, current):
    from dash import ctx
    if not ctx.triggered_id:
        return current
    return "submit" if ctx.triggered_id == "nav-submit" else "board"

@callback(Output("page-content", "children"), Input("current-page", "data"), Input("refresh-trigger", "data"))
def render_page(page, trigger):
    return create_submit_page() if page == "submit" else create_board_page()

@callback(
    Output("create-ticket-output", "children"),
    Output("ticket-title", "value"), Output("ticket-description", "value"),
    Output("ticket-email", "value"), Output("ticket-priority", "value"),
    Input("create-ticket-btn", "n_clicks"),
    State("ticket-title", "value"), State("ticket-description", "value"),
    State("ticket-email", "value"), State("ticket-priority", "value"),
    State("ticket-assignee", "value"), prevent_initial_call=True
)
def submit_ticket(n, title, desc, email, priority, assignee):
    if not engine or not table_exists:
        return dbc.Alert("Database not ready.", color="danger"), title, desc, email, priority
    if not all([title, desc, email, assignee]):
        return dbc.Alert("Please fill all fields including assignee.", color="warning"), title, desc, email, priority
    try:
        create_ticket(engine, title, desc, email, priority, assignee)
        return dbc.Alert("Ticket submitted successfully!", color="success"), "", "", "", "medium"
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger"), title, desc, email, priority

@callback(
    Output("column-open", "children"), Output("column-in_progress", "children"),
    Output("column-resolved", "children"), Output("column-closed", "children"),
    Output("count-open", "children"), Output("count-in_progress", "children"),
    Output("count-resolved", "children"), Output("count-closed", "children"),
    Input("refresh-interval", "n_intervals"), Input("update-trigger", "children"),
    Input("current-page", "data")
)
def update_board(n, trigger, page):
    empty = html.P("No tickets", style={"color": "#94a3b8", "fontSize": "13px", "textAlign": "center", "marginTop": "20px"})
    if page != "board" or not engine or not table_exists:
        return empty, empty, empty, empty, "0", "0", "0", "0"
    try:
        df = get_tickets(engine)
        results = []
        counts = []
        for status in ["open", "in_progress", "resolved", "closed"]:
            filtered = df[df['status'] == status] if not df.empty else pd.DataFrame()
            counts.append(str(len(filtered)))
            if filtered.empty:
                results.append(empty)
            else:
                cards = [create_ticket_card(row) for _, row in filtered.iterrows()]
                results.append(html.Div(cards))
        return results[0], results[1], results[2], results[3], counts[0], counts[1], counts[2], counts[3]
    except Exception:
        return empty, empty, empty, empty, "0", "0", "0", "0"

@callback(
    Output("update-modal", "is_open"), Output("selected-ticket-id", "children"),
    Output("modal-ticket-info", "children"), Output("modal-new-status", "value"),
    Output("update-trigger", "children"),
    Input({"type": "update-btn", "index": ALL}, "n_clicks"),
    Input("close-modal-btn", "n_clicks"), Input("update-ticket-btn", "n_clicks"),
    State("update-modal", "is_open"), State("selected-ticket-id", "children"),
    State("modal-new-status", "value"), prevent_initial_call=True
)
def handle_modal(update_clicks, close_clicks, confirm_clicks, is_open, selected_id, new_status):
    from dash import ctx
    import time as t
    
    if not ctx.triggered_id:
        return False, None, "", None, ""
    
    triggered = ctx.triggered[0]
    if not triggered.get("value"):
        return False, None, "", None, ""
    
    trigger_id = ctx.triggered_id
    
    if isinstance(trigger_id, dict) and trigger_id.get("type") == "update-btn":
        ticket_id = trigger_id["index"]
        try:
            df = get_tickets(engine)
            ticket = df[df['id'] == ticket_id].iloc[0]
            info = html.Div([
                html.H6(f"Ticket #{ticket['id']}: {ticket['title']}"),
                html.P(f"Current: {ticket['status'].replace('_', ' ').title()}", className="text-muted")
            ])
            return True, ticket_id, info, ticket['status'], ""
        except Exception:
            return False, None, "", None, ""
    
    if trigger_id == "update-ticket-btn" and selected_id:
        try:
            update_ticket_status(engine, int(selected_id), new_status)
            return False, None, "", None, str(t.time())
        except Exception:
            pass
        return False, None, "", None, ""
    
    if trigger_id == "close-modal-btn":
        return False, None, "", None, ""
    
    return False, None, "", None, ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
