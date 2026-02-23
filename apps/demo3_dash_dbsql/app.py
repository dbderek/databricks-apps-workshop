import os
import traceback
import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
from flask import request
import pandas as pd
from databricks import sdk
from databricks import sql

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server

# 1) Default Configuration
DEFAULT_WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "")
DEFAULT_CATALOG = os.environ.get("DATABRICKS_CATALOG", "main")
DEFAULT_SCHEMA = os.environ.get("DATABRICKS_SCHEMA", "default")

# 2) Helper functions for SDK initialization
def get_workspace_client():
    """Get WorkspaceClient with token from request headers."""
    try:
        token = request.headers.get("X-Forwarded-Access-Token")
        if not token:
            raise RuntimeError("X-Forwarded-Access-Token header not found in request")
        w = sdk.WorkspaceClient(token=token, auth_type="pat")
        return w
    except Exception as e:
        print(f"Failed to initialize Databricks SDK: {e}")
        print(traceback.format_exc())
        raise

# 3) Helper functions
def resolve_endpoint(warehouse_id: str):
    w = get_workspace_client()
    wh = w.warehouses.get(warehouse_id)
    host = wh.odbc_params.hostname
    http_path = wh.odbc_params.path
    return host, http_path

def get_oauth_token():
    """Get access token from request headers."""
    token = request.headers.get("X-Forwarded-Access-Token")
    if not token:
        raise RuntimeError("X-Forwarded-Access-Token header not found in request")
    return token

def get_current_user():
    w = get_workspace_client()
    current_user = w.current_user.me()
    return current_user.user_name

def get_connection(warehouse_id: str):
    host, http_path = resolve_endpoint(warehouse_id)
    token = get_oauth_token()
    conn = sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    )
    return conn

def exec_sql(conn, statement: str, params: dict | None = None):
    with conn.cursor() as cur:
        cur.execute(statement, params or {})
        try:
            return cur.fetchall()
        except Exception:
            return None

def ensure_table(conn, catalog, schema):
    table_name = f"{catalog}.{schema}.notes"
    exec_sql(conn, f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
          id BIGINT GENERATED ALWAYS AS IDENTITY,
          note STRING,
          created_by STRING,
          created_at TIMESTAMP DEFAULT current_timestamp()
        ) TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')
    """)
    return table_name

def list_notes(conn, table_name, limit: int = 20):
    rows = exec_sql(conn, f"""
        SELECT id, note, created_by, created_at
        FROM {table_name}
        ORDER BY created_at DESC
        LIMIT {limit}
    """)
    if not rows:
        return pd.DataFrame(columns=["id", "note", "created_by", "created_at"])
    return pd.DataFrame(rows, columns=["id", "note", "created_by", "created_at"])

def insert_note(conn, table_name, note: str, created_by: str):
    exec_sql(conn, f"INSERT INTO {table_name} (note, created_by) VALUES (%(note)s, %(created_by)s)", {"note": note, "created_by": created_by})

# Design Constants
COLORS = {
    'primary': '#FF3621', 'bg': '#F5F7FA', 'card': '#FFFFFF', 
    'text': '#1B3139', 'border': '#E0E0E0'
}
CARD_STYLE = {
    'backgroundColor': COLORS['card'], 'padding': '24px', 'borderRadius': '8px',
    'boxShadow': '0 2px 8px rgba(0,0,0,0.08)', 'marginBottom': '24px',
    'border': f"1px solid {COLORS['border']}"
}
BTN_STYLE = {
    'backgroundColor': COLORS['primary'], 'color': 'white', 'border': 'none',
    'padding': '10px 24px', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': '500'
}
INPUT_STYLE = {
    'width': '100%', 'padding': '8px 12px', 'borderRadius': '4px',
    'border': f"1px solid {COLORS['border']}", 'height': '40px'
}

# 4) Layout
app.layout = html.Div(style={'fontFamily': '-apple-system, system-ui, sans-serif', 'backgroundColor': COLORS['bg'], 'minHeight': '100vh', 'padding': '40px', 'color': COLORS['text']}, children=[
    html.Div(style={'maxWidth': '1000px', 'margin': '0 auto'}, children=[
        html.H1("Databricks SQL + Dash", style={'marginBottom': '32px', 'fontWeight': '700'}),
        
        # Connection Settings
        html.Div(style=CARD_STYLE, children=[
            html.H3("Connection Settings", style={'marginTop': '0', 'marginBottom': '20px'}),
            html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))', 'gap': '20px', 'marginBottom': '20px'}, children=[
                html.Div([html.Label("SQL Warehouse ID", style={'fontWeight': '500', 'marginBottom': '8px', 'display': 'block'}), 
                          dcc.Input(id='warehouse-id', value=DEFAULT_WAREHOUSE_ID, style=INPUT_STYLE)]),
                html.Div([html.Label("Catalog", style={'fontWeight': '500', 'marginBottom': '8px', 'display': 'block'}), 
                          dcc.Input(id='catalog', value=DEFAULT_CATALOG, style=INPUT_STYLE)]),
                html.Div([html.Label("Schema", style={'fontWeight': '500', 'marginBottom': '8px', 'display': 'block'}), 
                          dcc.Input(id='schema', value=DEFAULT_SCHEMA, style=INPUT_STYLE)]),
            ]),
            html.Button('Test Connection & Initialize', id='btn-connect', n_clicks=0, style=BTN_STYLE),
            html.Div(id='connection-status', style={'marginTop': '16px', 'fontSize': '14px', 'fontWeight': '500'})
        ]),

        # Add Note
        html.Div(style=CARD_STYLE, children=[
            html.H3("Add Note", style={'marginTop': '0', 'marginBottom': '20px'}),
            html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
                dcc.Input(id='note-input', placeholder='Hello, DBSQL 👋', style={**INPUT_STYLE, 'flex': '1'}),
                html.Button('Save Note', id='btn-save', n_clicks=0, style=BTN_STYLE),
            ]),
            html.Div(id='save-status', style={'marginTop': '16px', 'fontWeight': '500'})
        ]),

        # Recent Notes
        html.Div(style=CARD_STYLE, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '20px'}, children=[
                html.H3("Recent Notes", style={'margin': '0'}),
                html.Button('Refresh', id='btn-refresh', n_clicks=0, style={'background': 'none', 'border': 'none', 'color': COLORS['primary'], 'cursor': 'pointer', 'fontWeight': '500', 'fontSize': '14px'}),
            ]),
            html.Div(id='notes-table-container')
        ])
    ])
])

# 5) Callbacks

@callback(
    Output('connection-status', 'children'),
    Input('btn-connect', 'n_clicks'),
    State('warehouse-id', 'value'),
    State('catalog', 'value'),
    State('schema', 'value'),
    prevent_initial_call=True
)
def handle_connect(n_clicks, warehouse_id, catalog, schema):
    if not warehouse_id:
        return html.Span("Please provide a Warehouse ID.", style={'color': 'red'})
    try:
        conn = get_connection(warehouse_id)
        ensure_table(conn, catalog, schema)
        conn.close()
        return html.Span(f"Successfully connected! Table '{catalog}.{schema}.notes' ready.", style={'color': 'green'})
    except Exception as e:
        print(f"Connection error: {str(e)}")
        print(traceback.format_exc())
        return html.Span(f"Error: {str(e)}", style={'color': 'red'})

@callback(
    Output('save-status', 'children'),
    Output('note-input', 'value'),
    Output('btn-refresh', 'n_clicks'), # Trigger refresh
    Input('btn-save', 'n_clicks'),
    State('note-input', 'value'),
    State('warehouse-id', 'value'),
    State('catalog', 'value'),
    State('schema', 'value'),
    State('btn-refresh', 'n_clicks'),
    prevent_initial_call=True
)
def handle_save(n_clicks, note, warehouse_id, catalog, schema, refresh_clicks):
    if not note:
        return html.Span("Please enter a note.", style={'color': 'orange'}), dash.no_update, dash.no_update
    
    try:
        conn = get_connection(warehouse_id)
        table_name = f"{catalog}.{schema}.notes"
        current_user = get_current_user()
        insert_note(conn, table_name, note, current_user)
        conn.close()
        # Increment refresh clicks to trigger table update
        new_refresh = (refresh_clicks or 0) + 1
        return html.Span("Saved!", style={'color': 'green'}), "", new_refresh
    except Exception as e:
        print(f"Save error: {str(e)}")
        print(traceback.format_exc())
        return html.Span(f"Error saving: {str(e)}", style={'color': 'red'}), dash.no_update, dash.no_update

@callback(
    Output('notes-table-container', 'children'),
    Input('btn-refresh', 'n_clicks'),
    State('warehouse-id', 'value'),
    State('catalog', 'value'),
    State('schema', 'value'),
)
def update_table(n_clicks, warehouse_id, catalog, schema):
    if not warehouse_id:
        return html.Div("Please configure Warehouse ID.")
    
    try:
        conn = get_connection(warehouse_id)
        table_name = f"{catalog}.{schema}.notes"
        
        # We might need to ensure table/schema exists if the user skipped the "Connect" button
        # But for list_notes, let's just try query, if fails, explain.
        
        df = list_notes(conn, table_name)
        conn.close()
        
        if df.empty:
            return html.Div("No notes found.")
        
        # Using Dash DataTable for better presentation
        return dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in df.columns],
            style_table={'overflowX': 'auto', 'borderRadius': '4px', 'border': f"1px solid {COLORS['border']}"},
            style_as_list_view=True,
            style_cell={
                'textAlign': 'left', 'padding': '12px 16px', 'fontFamily': 'inherit',
                'borderBottom': f"1px solid {COLORS['border']}", 'color': COLORS['text']
            },
            style_header={
                'backgroundColor': '#F5F7FA', 'fontWeight': '600', 'borderBottom': f"2px solid {COLORS['border']}",
                'color': COLORS['text']
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFAFA'}
            ]
        )
        
    except Exception as e:
        print(f"Data loading error: {str(e)}")
        print(traceback.format_exc())
        return html.Span(f"Error loading data: {str(e)}", style={'color': 'red'})

if __name__ == '__main__':
    app.run_server(debug=True)