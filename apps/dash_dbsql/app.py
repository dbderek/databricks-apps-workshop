import os
import dash
from dash import dcc, html, Input, Output, State, callback, dash_table
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

# 2) Initialize SDK
try:
    w = sdk.WorkspaceClient()
except Exception as e:
    print(f"Failed to initialize Databricks SDK: {e}")
    w = None

# 3) Helper functions
def resolve_endpoint(warehouse_id: str):
    if not w:
        raise RuntimeError("SDK not initialized")
    wh = w.warehouses.get(warehouse_id)
    host = wh.odbc_params.hostname
    http_path = wh.odbc_params.path
    return host, http_path

def get_oauth_token():
    if not w:
        raise RuntimeError("SDK not initialized")
    return w.config.oauth_token().access_token

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
          created_at TIMESTAMP DEFAULT current_timestamp()
        )
    """)
    return table_name

def list_notes(conn, table_name, limit: int = 20):
    rows = exec_sql(conn, f"""
        SELECT id, note, created_at
        FROM {table_name}
        ORDER BY created_at DESC
        LIMIT {limit}
    """)
    if not rows:
        return pd.DataFrame(columns=["id", "note", "created_at"])
    return pd.DataFrame(rows, columns=["id", "note", "created_at"])

def insert_note(conn, table_name, note: str):
    exec_sql(conn, f"INSERT INTO {table_name} (note) VALUES (%(note)s)", {"note": note})

# 4) Layout
app.layout = html.Div(style={'fontFamily': 'sans-serif', 'maxWidth': '800px', 'margin': '0 auto', 'padding': '20px'}, children=[
    html.H1("Databricks SQL + Dash"),
    
    html.Div(style={'backgroundColor': '#f0f0f0', 'padding': '15px', 'borderRadius': '5px', 'marginBottom': '20px'}, children=[
        html.H3("Connection Settings"),
        html.Div([
            html.Label("SQL Warehouse ID:"),
            dcc.Input(id='warehouse-id', type='text', value=DEFAULT_WAREHOUSE_ID, style={'width': '100%', 'marginBottom': '10px'}),
        ]),
        html.Div([
            html.Label("Catalog:"),
            dcc.Input(id='catalog', type='text', value=DEFAULT_CATALOG, style={'width': '100%', 'marginBottom': '10px'}),
        ]),
        html.Div([
            html.Label("Schema:"),
            dcc.Input(id='schema', type='text', value=DEFAULT_SCHEMA, style={'width': '100%', 'marginBottom': '10px'}),
        ]),
        html.Button('Test Connection & Initialize', id='btn-connect', n_clicks=0),
        html.Div(id='connection-status', style={'marginTop': '10px'})
    ]),

    html.Div(style={'borderTop': '2px solid #eee', 'paddingTop': '20px', 'marginBottom': '20px'}, children=[
        html.H3("Add Note"),
        html.Div([
            dcc.Input(id='note-input', type='text', placeholder='Hello, DBSQL 👋', style={'width': '70%', 'padding': '8px', 'marginRight': '10px'}),
            html.Button('Save Note', id='btn-save', n_clicks=0, style={'padding': '8px 15px'}),
        ], style={'display': 'flex', 'alignItems': 'center'}),
        html.Div(id='save-status', style={'marginTop': '10px', 'fontWeight': 'bold'})
    ]),

    html.Div([
        html.Div([
            html.H3("Recent Notes", style={'display': 'inline-block', 'marginRight': '20px'}),
            html.Button('Refresh', id='btn-refresh', n_clicks=0),
        ], style={'marginBottom': '15px'}),
        html.Div(id='notes-table-container')
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
        insert_note(conn, table_name, note)
        conn.close()
        # Increment refresh clicks to trigger table update
        new_refresh = (refresh_clicks or 0) + 1
        return html.Span("Saved!", style={'color': 'green'}), "", new_refresh
    except Exception as e:
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
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'fontFamily': 'sans-serif'
            },
            style_header={
                'backgroundColor': 'rgb(230, 230, 230)',
                'fontWeight': 'bold'
            }
        )
        
    except Exception as e:
        return html.Span(f"Error loading data: {str(e)}", style={'color': 'red'})

if __name__ == '__main__':
    app.run_server(debug=True)