import os
import time
import uuid
from dash import Dash, html, dcc, Input, Output, State, callback, dash_table, ALL
import dash_bootstrap_components as dbc
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from databricks import sdk
from datetime import datetime
import pandas as pd

# Initialize Databricks SDK
w = sdk.WorkspaceClient()

# Debug: Print all PG-related environment variables
print("=== Database Environment Variables ===")
for key, value in sorted(os.environ.items()):
    if 'PG' in key.upper() or 'DATABASE' in key.upper() or 'DB' in key.upper():
        # Mask sensitive values
        if 'PASSWORD' in key.upper() or 'TOKEN' in key.upper():
            print(f"  {key}: ***masked***")
        else:
            print(f"  {key}: {value}")
print("=" * 40)

# Read Postgres params from environment (injected by Databricks App Database resource)
PGHOST = os.environ.get("PGHOST", "")
PGDATABASE = os.environ.get("PGDATABASE", "")
PGUSER = os.environ.get("PGUSER", "")
PGPORT = os.environ.get("PGPORT", "5432")
PGSSLMODE = os.environ.get("PGSSLMODE", "require")

# Lakebase table configuration
# Using "public" schema which exists by default in PostgreSQL
LAKEBASE_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "public")
LAKEBASE_TABLE = os.environ.get("LAKEBASE_TABLE", "support_tickets")

# Validation
missing = [k for k, v in [("PGHOST", PGHOST), ("PGDATABASE", PGDATABASE), ("PGUSER", PGUSER)] if not v]
if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
else:
    print(f"Database config: host={PGHOST}, db={PGDATABASE}, user={PGUSER}")

def db_url_without_password() -> str:
    return f"postgresql+psycopg://{PGUSER}:@{PGHOST}:{PGPORT}/{PGDATABASE}"

# Get Lakebase instance name from PGHOST (format: <instance-name>.<region>.lakebase.databricks.com)
def get_instance_name_from_host(host: str) -> str:
    """Extract instance name from Lakebase hostname."""
    if host:
        return host.split('.')[0]
    return ""

LAKEBASE_INSTANCE_NAME = get_instance_name_from_host(PGHOST)
print(f"Detected Lakebase instance name: {LAKEBASE_INSTANCE_NAME}")

def get_engine() -> Engine:
    engine = create_engine(
        db_url_without_password(),
        pool_pre_ping=True,
        connect_args={"sslmode": PGSSLMODE},
    )
    
    # Token refresh mechanism using database credential generation
    token_cache = {"value": None, "ts": 0}
    refresh_secs = 15 * 60  # Refresh token every 15 minutes
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        now = time.time()
        if token_cache["value"] is None or (now - token_cache["ts"]) > refresh_secs:
            try:
                # Try using database credential generation (preferred for Lakebase)
                cred = w.database.generate_database_credential(
                    request_id=str(uuid.uuid4()),
                    instance_names=[LAKEBASE_INSTANCE_NAME]
                )
                token_cache["value"] = cred.token
                print(f"Generated database credential for instance: {LAKEBASE_INSTANCE_NAME}")
            except Exception as e:
                print(f"Warning: generate_database_credential failed ({e}), falling back to oauth_token")
                try:
                    token_cache["value"] = w.config.oauth_token().access_token
                except Exception as e2:
                    print(f"Error getting oauth_token: {e2}")
                    raise
            token_cache["ts"] = now
        cparams["password"] = token_cache["value"]
    
    return engine

# Get current user for ticket assignment
CURRENT_USER = PGUSER  # The PostgreSQL user (email) for this session

# Check if table exists (don't create - setup notebook handles that)
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

def debug_database_state(engine: Engine):
    """Debug database connection and table state."""
    try:
        with engine.begin() as conn:
            # Check current database and user
            result = conn.execute(text("SELECT current_database(), current_user, current_schema()")).fetchone()
            print(f"=== Database Debug Info ===")
            print(f"  Connected to database: {result[0]}")
            print(f"  Connected as user: {result[1]}")
            print(f"  Current schema: {result[2]}")
            
            # List all schemas
            schemas = conn.execute(text("SELECT schema_name FROM information_schema.schemata")).fetchall()
            print(f"  Available schemas: {[s[0] for s in schemas]}")
            
            # List all tables (no filter)
            tables = conn.execute(text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)).fetchall()
            
            if tables:
                print(f"  Tables found:")
                for t in tables:
                    print(f"    - {t[0]}.{t[1]}")
            else:
                print(f"  No user tables found!")
            
            # Try direct query on expected table
            print(f"\n  Checking for table: {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}")
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}")).scalar()
                print(f"  Direct query SUCCESS! Row count: {count}")
            except Exception as table_err:
                print(f"  Direct query FAILED: {table_err}")
            
            print("=" * 40)
    except Exception as e:
        print(f"Debug error: {e}")

TABLE_MISSING_WARNING = f"""
⚠️ Table '{LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}' does not exist!

Please run the setup notebook before using this app:
  apps/support_tickets_dash/setup-lakebase.ipynb

This notebook will create the Lakebase instance, table, and seed data.
"""

def get_tickets(engine: Engine, status_filter=None):
    """Fetch tickets from database.
    
    Note: Row-level security (RLS) is enabled on this table.
    Users will only see tickets where assigned_to matches their username.
    """
    sql = f"""
    SELECT id, title, description, customer_email, status, priority, assigned_to, created_at, updated_at
    FROM {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
    """
    if status_filter and status_filter != "all":
        sql += " WHERE status = :status"
    sql += " ORDER BY created_at DESC"
    
    with engine.begin() as conn:
        params = {"status": status_filter} if status_filter and status_filter != "all" else {}
        result = conn.execute(text(sql), params).mappings().all()
        return pd.DataFrame(result) if result else pd.DataFrame()

def create_ticket(engine: Engine, title, description, customer_email, priority):
    """Create a new support ticket assigned to the current user."""
    sql = f"""
    INSERT INTO {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} (title, description, customer_email, priority, status, assigned_to)
    VALUES (:title, :desc, :email, :priority, 'open', :assigned_to)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "title": title,
            "desc": description,
            "email": customer_email,
            "priority": priority,
            "assigned_to": CURRENT_USER
        })

def update_ticket_status(engine: Engine, ticket_id, new_status):
    """Update ticket status"""
    sql = f"""
    UPDATE {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}
    SET status = :status, updated_at = now()
    WHERE id = :id
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"status": new_status, "id": ticket_id})

# Initialize engine and check table exists
engine = None
table_exists = False
init_error = None

try:
    if missing:
        raise ValueError(f"Cannot initialize database - missing env vars: {', '.join(missing)}")
    engine = get_engine()
    print("Engine created successfully, checking table exists...")
    table_exists = check_table_exists(engine)
    if table_exists:
        print(f"Table verified: {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}")
    else:
        print(f"WARNING: Table {LAKEBASE_SCHEMA}.{LAKEBASE_TABLE} does not exist according to information_schema!")
        print("Running detailed debug...")
        debug_database_state(engine)
except Exception as e:
    import traceback
    init_error = str(e)
    print(f"Database initialization error: {e}")
    print(f"Traceback:\n{traceback.format_exc()}")

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Support Ticket System"

# Define status colors
status_colors = {
    "open": "danger",
    "in_progress": "warning",
    "resolved": "success",
    "closed": "secondary"
}

priority_colors = {
    "low": "info",
    "medium": "warning",
    "high": "danger",
    "critical": "dark"
}

# Build warning alert if needed
def get_warning_alert():
    if init_error:
        return dbc.Alert([
            html.H4("⚠️ Database Connection Error", className="alert-heading"),
            html.P(f"Error: {init_error}"),
            html.Hr(),
            html.P([
                "Please ensure the database resource is configured correctly and run ",
                html.Code("apps/support_tickets_dash/setup-lakebase.ipynb"),
                " to create the Lakebase instance and table."
            ], className="mb-0")
        ], color="danger", className="mb-4")
    elif not table_exists:
        return dbc.Alert([
            html.H4("⚠️ Table Not Found", className="alert-heading"),
            html.P(f"The table '{LAKEBASE_SCHEMA}.{LAKEBASE_TABLE}' does not exist."),
            html.Hr(),
            html.P([
                "Please run ",
                html.Code("apps/support_tickets_dash/setup-lakebase.ipynb"),
                " in Databricks to create the Lakebase instance, table, and seed data before using this app."
            ], className="mb-0")
        ], color="warning", className="mb-4")
    return None

warning_alert = get_warning_alert()

# Layout
app.layout = dbc.Container([
    # Warning banner (if any)
    warning_alert if warning_alert else html.Div(),
    
    dbc.Row([
        dbc.Col([
            html.H1("🎫 Support Ticket System", className="text-center mb-4 mt-4"),
            html.P([
                f"Powered by Databricks Lakebase • Logged in as: ",
                html.Strong(CURRENT_USER)
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
        
        # Right column - View Tickets
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H4("📋 My Tickets"), width=6),
                        dbc.Col([
                            dbc.Select(
                                id="status-filter",
                                options=[
                                    {"label": "All My Tickets", "value": "all"},
                                    {"label": "🔴 Open", "value": "open"},
                                    {"label": "🟡 In Progress", "value": "in_progress"},
                                    {"label": "🟢 Resolved", "value": "resolved"},
                                    {"label": "⚫ Closed", "value": "closed"}
                                ],
                                value="all"
                            )
                        ], width=6)
                    ])
                ]),
                dbc.CardBody([
                    dcc.Interval(id="refresh-interval", interval=5000, n_intervals=0),
                    html.Div(id="tickets-container")
                ])
            ])
        ], width=8)
    ], className="mb-4"),
    
    # Update ticket modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Update Ticket Status")),
        dbc.ModalBody([
            html.Div(id="modal-ticket-info"),
            dbc.Label("New Status", className="mt-3"),
            dbc.Select(
                id="modal-new-status",
                options=[
                    {"label": "🔴 Open", "value": "open"},
                    {"label": "🟡 In Progress", "value": "in_progress"},
                    {"label": "🟢 Resolved", "value": "resolved"},
                    {"label": "⚫ Closed", "value": "closed"}
                ]
            )
        ]),
        dbc.ModalFooter([
            dbc.Button("Update", id="update-ticket-btn", color="primary"),
            dbc.Button("Close", id="close-modal-btn", color="secondary")
        ])
    ], id="update-modal", is_open=False),
    
    # Hidden div to store selected ticket ID
    html.Div(id="selected-ticket-id", style={"display": "none"})
    
], fluid=True, className="py-3")

# Callbacks
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
        return dbc.Alert("Database not ready. Please run setup-lakebase.ipynb first.", color="danger"), title, description, email, priority
    
    if not all([title, description, email]):
        return dbc.Alert("Please fill in all fields", color="warning"), title, description, email, priority
    
    try:
        create_ticket(engine, title, description, email, priority)
        return dbc.Alert("✅ Ticket created successfully!", color="success"), "", "", "", "medium"
    except Exception as e:
        return dbc.Alert(f"❌ Error: {str(e)}", color="danger"), title, description, email, priority

@callback(
    Output("tickets-container", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("status-filter", "value"),
    Input("create-ticket-btn", "n_clicks"),
    Input("update-ticket-btn", "n_clicks")
)
def update_tickets_display(n, status_filter, create_clicks, update_clicks):
    # Check if database is ready
    if engine is None:
        return dbc.Alert([
            html.Strong("Database not connected. "),
            "Please check the logs and ensure the database resource is configured."
        ], color="danger")
    
    if not table_exists:
        return dbc.Alert([
            html.Strong("Table not found. "),
            html.Span("Please run "),
            html.Code("setup-lakebase.ipynb"),
            html.Span(" to initialize the database.")
        ], color="warning")
    
    try:
        df = get_tickets(engine, status_filter)
        
        if df.empty:
            return dbc.Alert("No tickets found. Create your first ticket using the form on the left!", color="info")
        
        # Create ticket cards
        tickets = []
        for _, row in df.iterrows():
            ticket_card = dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col([
                            html.Strong(f"#{row['id']} - {row['title']}")
                        ], width=7),
                        dbc.Col([
                            dbc.Badge(row['status'].replace('_', ' ').title(), color=status_colors.get(row['status'], "secondary"), className="me-2"),
                            dbc.Badge(row['priority'].title(), color=priority_colors.get(row['priority'], "info"))
                        ], width=5, className="text-end")
                    ])
                ]),
                dbc.CardBody([
                    html.P(row['description'], className="mb-2"),
                    html.Small([
                        html.I(className="bi bi-envelope me-1"),
                        row['customer_email'],
                        " • ",
                        html.I(className="bi bi-clock me-1"),
                        row['created_at'].strftime('%Y-%m-%d %H:%M') if hasattr(row['created_at'], 'strftime') else str(row['created_at'])
                    ], className="text-muted"),
                    html.Div([
                        dbc.Button("Update Status", id={"type": "update-btn", "index": row['id']}, size="sm", color="primary", className="mt-2")
                    ])
                ])
            ], className="mb-3")
            tickets.append(ticket_card)
        
        return tickets
    except Exception as e:
        return dbc.Alert(f"Error loading tickets: {str(e)}", color="danger")

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
    
    if engine is None or not table_exists:
        return False, None, "", None
    
    trigger_id = callback_context.triggered[0]["prop_id"]
    
    # If update button clicked
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
        except Exception as e:
            print(f"Error opening modal: {e}")
            return False, None, "", None
    
    # If confirm update clicked
    if "update-ticket-btn" in trigger_id and selected_id:
        try:
            update_ticket_status(engine, int(selected_id), new_status)
            return False, None, "", None
        except Exception as e:
            print(f"Error updating ticket: {e}")
            return False, None, "", None
    
    # Close modal
    return False, None, "", None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
