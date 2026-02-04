import os
import time
from dash import Dash, html, dcc, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from databricks import sdk
from datetime import datetime
import pandas as pd
from flask import request

# Initialize Databricks SDK
w = sdk.WorkspaceClient()

# Read Postgres params from environment (injected by Databricks App Database resource)
PGHOST = os.environ.get("PGHOST", "")
PGDATABASE = os.environ.get("PGDATABASE", "")
PGUSER = os.environ.get("PGUSER", "")
PGPORT = os.environ.get("PGPORT", "5432")
PGSSLMODE = os.environ.get("PGSSLMODE", "require")

# Lakebase table configuration
LAKEBASE_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "public")
LAKEBASE_TABLE = os.environ.get("LAKEBASE_TABLE", "support_tickets")

# Validation
missing = [k for k, v in [("PGHOST", PGHOST), ("PGDATABASE", PGDATABASE), ("PGUSER", PGUSER)] if not v]
if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")

def db_url_without_password() -> str:
    return f"postgresql+psycopg://{PGUSER}:@{PGHOST}:{PGPORT}/{PGDATABASE}"

def get_engine() -> Engine:
    """Create a SQLAlchemy engine that uses the end-user's credentials.
    
    With 'on behalf of user authorization' enabled in Databricks Apps,
    the user's access token is available via X-Forwarded-Access-Token header.
    This enables PostgreSQL RLS to work correctly based on current_user.
    """
    engine = create_engine(
        db_url_without_password(),
        pool_pre_ping=True,
        poolclass=NullPool,  # Disable pooling for per-user connections
        connect_args={"sslmode": PGSSLMODE},
    )
    
    # Fallback token cache for initialization (when no request context)
    fallback_token_cache = {"value": None, "ts": 0}
    refresh_secs = 15 * 60
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        """Provide user credentials for each connection."""
        try:
            # Get user credentials from request headers
            user_email = request.headers.get('X-Forwarded-Email')
            user_token = request.headers.get('X-Forwarded-Access-Token')
            
            if user_email and user_token:
                cparams["user"] = user_email
                cparams["password"] = user_token
                return
        except RuntimeError:
            pass  # No request context
        
        # Fallback to service principal for initialization
        now = time.time()
        if fallback_token_cache["value"] is None or (now - fallback_token_cache["ts"]) > refresh_secs:
            try:
                fallback_token_cache["value"] = w.config.oauth_token().access_token
            except Exception:
                pass
            fallback_token_cache["ts"] = now
        cparams["password"] = fallback_token_cache["value"]
    
    return engine

def get_current_user():
    """Get the current user's email from request headers."""
    try:
        return request.headers.get('X-Forwarded-Email', 'Unknown')
    except RuntimeError:
        return 'Unknown'

# Check if table exists
def check_table_exists(engine: Engine) -> bool:
    """Check if the support tickets table exists."""
    sql = """
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = :schema AND table_name = :table
    );
    """
    with engine.begin() as conn:
        result = conn.execute(text(sql), {"schema": LAKEBASE_SCHEMA, "table": LAKEBASE_TABLE}).scalar()
        return result

def get_tickets(engine: Engine, status_filter=None):
    """Fetch tickets from database.
    
    RLS filters automatically based on current_user (the connected user's email).
    """
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

def create_ticket(engine: Engine, title, description, customer_email, priority):
    """Create a new support ticket assigned to the current user."""
    sql = f"""
    INSERT INTO {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} (title, description, customer_email, priority, status, assigned_to)
    VALUES (:title, :desc, :email, :priority, 'open', current_user)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "title": title,
            "desc": description,
            "email": customer_email,
            "priority": priority
        })

def update_ticket_status(engine: Engine, ticket_id, new_status):
    """Update ticket status."""
    sql = f"""
    UPDATE {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
    SET status = :status, updated_at = now()
    WHERE id = :id
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"status": new_status, "id": ticket_id})

# Initialize engine and check table
engine = None
table_exists = False
init_error = None

try:
    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")
    engine = get_engine()
    table_exists = check_table_exists(engine)
    if table_exists:
        print(f"Table verified: {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}")
    else:
        print(f"Table not found: {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}")
except Exception as e:
    init_error = str(e)
    print(f"Database initialization error: {e}")

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Support Ticket System"

# Status/priority colors
status_colors = {"open": "danger", "in_progress": "warning", "resolved": "success", "closed": "secondary"}
priority_colors = {"low": "info", "medium": "warning", "high": "danger", "critical": "dark"}

# Warning alert helper
def get_warning_alert():
    if init_error:
        return dbc.Alert([
            html.H4("Database Connection Error", className="alert-heading"),
            html.P(f"Error: {init_error}"),
        ], color="danger", className="mb-4")
    elif not table_exists:
        return dbc.Alert([
            html.H4("Table Not Found", className="alert-heading"),
            html.P(f"Please run setup-lakebase.ipynb to create the table."),
        ], color="warning", className="mb-4")
    return None

warning_alert = get_warning_alert()

# Layout
app.layout = dbc.Container([
    warning_alert if warning_alert else html.Div(),
    
    dbc.Row([
        dbc.Col([
            html.H1("🎫 Support Ticket System", className="text-center mb-4 mt-4"),
            html.P([
                "Powered by Databricks Lakebase • Logged in as: ",
                html.Strong(id="current-user-display")
            ], className="text-center text-muted mb-4")
        ])
    ]),
    
    dbc.Row([
        # Left column - Create Ticket
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("📝 Create New Ticket")),
                dbc.CardBody([
                    dbc.Label("Title"),
                    dbc.Input(id="ticket-title", placeholder="Brief description of the issue", className="mb-3"),
                    
                    dbc.Label("Description"),
                    dbc.Textarea(id="ticket-description", placeholder="Detailed description...", className="mb-3", rows=4),
                    
                    dbc.Label("Customer Email"),
                    dbc.Input(id="ticket-email", type="email", placeholder="customer@example.com", className="mb-3"),
                    
                    dbc.Label("Priority"),
                    dbc.Select(
                        id="ticket-priority",
                        options=[
                            {"label": "🟢 Low", "value": "low"},
                            {"label": "🟡 Medium", "value": "medium"},
                            {"label": "🔴 High", "value": "high"},
                            {"label": "⚫ Critical", "value": "critical"}
                        ],
                        value="medium",
                        className="mb-3"
                    ),
                    
                    dbc.Button("Create Ticket", id="create-ticket-btn", color="primary", className="w-100"),
                    html.Div(id="create-ticket-output", className="mt-3")
                ])
            ])
        ], width=4),
        
        # Right column - Tickets List
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H4("📋 My Tickets"), width=6),
                        dbc.Col([
                            dbc.Select(
                                id="status-filter",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Open", "value": "open"},
                                    {"label": "In Progress", "value": "in_progress"},
                                    {"label": "Resolved", "value": "resolved"},
                                    {"label": "Closed", "value": "closed"}
                                ],
                                value="all",
                                size="sm"
                            )
                        ], width=6)
                    ])
                ]),
                dbc.CardBody([
                    html.Div(id="tickets-container", style={"maxHeight": "600px", "overflowY": "auto"})
                ])
            ])
        ], width=8)
    ]),
    
    # Update Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Update Ticket Status")),
        dbc.ModalBody([
            html.Div(id="modal-ticket-info"),
            html.Hr(),
            dbc.Label("New Status"),
            dbc.Select(
                id="modal-new-status",
                options=[
                    {"label": "Open", "value": "open"},
                    {"label": "In Progress", "value": "in_progress"},
                    {"label": "Resolved", "value": "resolved"},
                    {"label": "Closed", "value": "closed"}
                ]
            )
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="close-modal-btn", className="me-2"),
            dbc.Button("Update", id="update-ticket-btn", color="primary")
        ])
    ], id="update-modal", is_open=False),
    
    html.Div(id="selected-ticket-id", style={"display": "none"}),
    dcc.Interval(id="refresh-interval", interval=30000, n_intervals=0)
    
], fluid=True, className="py-3")

# Callbacks
@callback(
    Output("current-user-display", "children"),
    Input("refresh-interval", "n_intervals")
)
def update_user_display(n):
    return get_current_user()

@callback(
    Output("create-ticket-output", "children"),
    Output("ticket-title", "value"),
    Output("ticket-description", "value"),
    Output("ticket-email", "value"),
    Output("ticket-priority", "value"),
    Input("create-ticket-btn", "n_clicks"),
    State("ticket-title", "value"),
    State("ticket-description", "value"),
    State("ticket-email", "value"),
    State("ticket-priority", "value"),
    prevent_initial_call=True
)
def create_new_ticket(n_clicks, title, description, email, priority):
    if engine is None or not table_exists:
        return dbc.Alert("Database not ready.", color="danger"), title, description, email, priority
    
    if not all([title, description, email]):
        return dbc.Alert("Please fill in all fields", color="warning"), title, description, email, priority
    
    try:
        create_ticket(engine, title, description, email, priority)
        return dbc.Alert("✅ Ticket created!", color="success"), "", "", "", "medium"
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger"), title, description, email, priority

@callback(
    Output("tickets-container", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("status-filter", "value"),
    Input("create-ticket-btn", "n_clicks"),
    Input("update-ticket-btn", "n_clicks")
)
def update_tickets_display(n, status_filter, create_clicks, update_clicks):
    if engine is None:
        return dbc.Alert("Database not connected.", color="danger")
    
    if not table_exists:
        return dbc.Alert("Table not found. Run setup-lakebase.ipynb first.", color="warning")
    
    try:
        df = get_tickets(engine, status_filter)
        
        if df.empty:
            return dbc.Alert("No tickets found. Create your first ticket!", color="info")
        
        tickets = []
        for _, row in df.iterrows():
            ticket_card = dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.Strong(f"#{row['id']} - {row['title']}"), width=7),
                        dbc.Col([
                            dbc.Badge(row['status'].replace('_', ' ').title(), 
                                     color=status_colors.get(row['status'], "secondary"), className="me-2"),
                            dbc.Badge(row['priority'].title(), 
                                     color=priority_colors.get(row['priority'], "info"))
                        ], width=5, className="text-end")
                    ])
                ]),
                dbc.CardBody([
                    html.P(row['description'], className="mb-2"),
                    html.Small([
                        row['customer_email'], " • ",
                        row['created_at'].strftime('%Y-%m-%d %H:%M') if hasattr(row['created_at'], 'strftime') else str(row['created_at'])
                    ], className="text-muted"),
                    html.Div([
                        dbc.Button("Update Status", id={"type": "update-btn", "index": row['id']}, 
                                  size="sm", color="primary", className="mt-2")
                    ])
                ])
            ], className="mb-3")
            tickets.append(ticket_card)
        
        return tickets
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")

@callback(
    Output("update-modal", "is_open"),
    Output("selected-ticket-id", "children"),
    Output("modal-ticket-info", "children"),
    Output("modal-new-status", "value"),
    Input({"type": "update-btn", "index": ALL}, "n_clicks"),
    Input("close-modal-btn", "n_clicks"),
    Input("update-ticket-btn", "n_clicks"),
    State("update-modal", "is_open"),
    State("selected-ticket-id", "children"),
    State("modal-new-status", "value"),
    prevent_initial_call=True
)
def toggle_modal(update_clicks, close_clicks, confirm_clicks, is_open, selected_id, new_status):
    from dash import callback_context
    
    if not callback_context.triggered:
        return False, None, "", None
    
    # Get the trigger info
    triggered = callback_context.triggered[0]
    trigger_id = triggered["prop_id"]
    trigger_value = triggered["value"]
    
    # Ignore if no actual click happened (value is None or 0)
    if not trigger_value:
        return False, None, "", None
    
    if engine is None or not table_exists:
        return False, None, "", None
    
    # Handle update button click on a ticket card
    if "update-btn" in trigger_id:
        try:
            ticket_id = eval(trigger_id.split(".")[0])["index"]
            df = get_tickets(engine)
            ticket = df[df['id'] == ticket_id].iloc[0]
            
            info = html.Div([
                html.H5(f"Ticket #{ticket['id']}: {ticket['title']}"),
                html.P(f"Current Status: {ticket['status'].replace('_', ' ').title()}")
            ])
            
            return True, ticket_id, info, ticket['status']
        except Exception:
            return False, None, "", None
    
    # Handle confirm update button in modal
    if "update-ticket-btn" in trigger_id and selected_id:
        try:
            update_ticket_status(engine, int(selected_id), new_status)
        except Exception:
            pass
        return False, None, "", None
    
    # Handle close/cancel button
    if "close-modal-btn" in trigger_id:
        return False, None, "", None
    
    return False, None, "", None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
