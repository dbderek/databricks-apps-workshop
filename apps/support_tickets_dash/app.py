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
app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)
app.title = "Support Tickets"

# Styles
CARD_STYLE = {"borderRadius": "8px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"}
TICKET_CARD_STYLE = {"borderRadius": "6px", "marginBottom": "8px", "boxShadow": "0 1px 3px rgba(0,0,0,0.08)"}
COLUMN_STYLE = {"backgroundColor": "#f8f9fa", "borderRadius": "8px", "padding": "12px", "minHeight": "400px"}

status_colors = {"open": "danger", "in_progress": "warning", "resolved": "success", "closed": "secondary"}
priority_colors = {"low": "info", "medium": "warning", "high": "danger", "critical": "dark"}

def create_navbar(current_page):
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("Support Tickets", className="fw-bold"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Submit Ticket", href="#", id="nav-submit", 
                    active=current_page == "submit", className="px-3")),
                dbc.NavItem(dbc.NavLink("My Tickets", href="#", id="nav-board", 
                    active=current_page == "board", className="px-3")),
            ], className="ms-auto"),
            html.Div(id="user-display", className="text-muted ms-3 small")
        ], fluid=True),
        color="white", className="border-bottom mb-4", style={"boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}
    )

def create_submit_page():
    users = get_all_users(engine) if engine and table_exists else []
    user_options = [{"label": u, "value": u} for u in users]
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Submit a Support Ticket", className="mb-0")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Title", className="fw-medium"),
                                dbc.Input(id="ticket-title", placeholder="Brief summary of the issue", className="mb-3"),
                            ], md=12),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Description", className="fw-medium"),
                                dbc.Textarea(id="ticket-description", placeholder="Detailed description of the issue...", 
                                           rows=4, className="mb-3"),
                            ], md=12),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Your Email", className="fw-medium"),
                                dbc.Input(id="ticket-email", type="email", placeholder="you@example.com", className="mb-3"),
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Priority", className="fw-medium"),
                                dbc.Select(id="ticket-priority", options=[
                                    {"label": "Low", "value": "low"},
                                    {"label": "Medium", "value": "medium"},
                                    {"label": "High", "value": "high"},
                                    {"label": "Critical", "value": "critical"}
                                ], value="medium", className="mb-3"),
                            ], md=6),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Assign To", className="fw-medium"),
                                dbc.Select(id="ticket-assignee", options=user_options,
                                          placeholder="Select team member...", className="mb-3"),
                            ], md=12),
                        ]),
                        dbc.Button("Submit Ticket", id="create-ticket-btn", color="primary", className="w-100 mt-2"),
                        html.Div(id="create-ticket-output", className="mt-3")
                    ])
                ], style=CARD_STYLE)
            ], md=6, className="mx-auto")
        ], className="justify-content-center")
    ], fluid=True)

def create_ticket_card(row):
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(f"#{row['id']}", className="text-muted small me-2"),
                dbc.Badge(row['priority'].title(), color=priority_colors.get(row['priority'], "secondary"), 
                         className="float-end", style={"fontSize": "10px"})
            ]),
            html.H6(row['title'], className="mt-1 mb-2", style={"fontSize": "14px"}),
            html.P(row['description'][:80] + "..." if len(row['description']) > 80 else row['description'],
                  className="text-muted small mb-2", style={"fontSize": "12px"}),
            html.Div([
                html.Small(row['customer_email'], className="text-muted"),
            ]),
            dbc.Button("Update", id={"type": "update-btn", "index": row['id']}, 
                      size="sm", color="outline-primary", className="mt-2 w-100")
        ], className="p-2")
    ], style=TICKET_CARD_STYLE)

def create_board_page():
    if not engine or not table_exists:
        return dbc.Container([
            dbc.Alert("Database not configured. Please run setup-lakebase.ipynb first.", color="warning")
        ])
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([html.Div(id="board-open", style=COLUMN_STYLE)], md=3),
            dbc.Col([html.Div(id="board-in-progress", style=COLUMN_STYLE)], md=3),
            dbc.Col([html.Div(id="board-resolved", style=COLUMN_STYLE)], md=3),
            dbc.Col([html.Div(id="board-closed", style=COLUMN_STYLE)], md=3),
        ], className="g-3"),
        
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Update Status")),
            dbc.ModalBody([
                html.Div(id="modal-ticket-info"),
                html.Hr(),
                dbc.Label("New Status"),
                dbc.Select(id="modal-new-status", options=[
                    {"label": "Open", "value": "open"},
                    {"label": "In Progress", "value": "in_progress"},
                    {"label": "Resolved", "value": "resolved"},
                    {"label": "Closed", "value": "closed"}
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="close-modal-btn", color="secondary", className="me-2"),
                dbc.Button("Update", id="update-ticket-btn", color="primary")
            ])
        ], id="update-modal", is_open=False),
        
        html.Div(id="selected-ticket-id", style={"display": "none"}),
        html.Div(id="update-trigger", style={"display": "none"})
    ], fluid=True)

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

def create_column_content(df, status, label):
    filtered = df[df['status'] == status] if not df.empty else pd.DataFrame()
    count = len(filtered)
    cards = [create_ticket_card(row) for _, row in filtered.iterrows()] if not filtered.empty else []
    return html.Div([
        html.Div([
            html.H6(label, className="mb-0 fw-bold"),
            dbc.Badge(str(count), color=status_colors.get(status, "secondary"), className="ms-2")
        ], className="d-flex align-items-center mb-3"),
        html.Div(cards if cards else [html.P("No tickets", className="text-muted small text-center")])
    ])

@callback(
    Output("board-open", "children"), Output("board-in-progress", "children"),
    Output("board-resolved", "children"), Output("board-closed", "children"),
    Input("refresh-interval", "n_intervals"), Input("update-trigger", "children"),
    Input("current-page", "data")
)
def update_board(n, trigger, page):
    if page != "board" or not engine or not table_exists:
        return [html.Div()]*4
    try:
        df = get_tickets(engine)
        return (
            create_column_content(df, "open", "Open"),
            create_column_content(df, "in_progress", "In Progress"),
            create_column_content(df, "resolved", "Resolved"),
            create_column_content(df, "closed", "Closed")
        )
    except Exception:
        return [html.Div()]*4

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
