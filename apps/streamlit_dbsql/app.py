import os
import time
import streamlit as st
import pandas as pd
from databricks import sdk
from databricks import sql

st.set_page_config(page_title="Streamlit + Databricks SQL (SDK token)", layout="centered")

# 1) Inputs
# Provide the SQL Warehouse ID via env var or sidebar.
WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "")

# Unity Catalog location to create/read the demo table.
CATALOG = os.environ.get("DATABRICKS_CATALOG", "main")
SCHEMA = os.environ.get("DATABRICKS_SCHEMA", "default")
TABLE = f"{CATALOG}.{SCHEMA}.notes"

with st.sidebar:
    st.header("Connection")
    WAREHOUSE_ID = st.text_input("SQL Warehouse ID", value=WAREHOUSE_ID, placeholder="e.g. 1234abcd...")

# 2) Initialize SDK (uses app identity when running in Databricks Apps)
try:
    w = sdk.WorkspaceClient()
except Exception as e:
    st.error(f"Failed to initialize Databricks SDK: {e}")
    st.stop()

# 3) Resolve Warehouse host + http_path and an OAuth token
def resolve_endpoint(warehouse_id: str):
    if not warehouse_id:
        raise ValueError("Missing SQL Warehouse ID. Provide it via SQL_WAREHOUSE_ID env var or the sidebar.")
    wh = w.warehouses.get(warehouse_id)
    # The SDK exposes ODBC/HTTP parameters for the endpoint:
    host = wh.odbc_params.hostname
    http_path = wh.odbc_params.path
    return host, http_path

def get_oauth_token():
    # Short-lived OAuth token managed by the SDK
    return w.config.oauth_token().access_token

@st.cache_resource(show_spinner=False)
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

def init_objects(conn):
    # Create schema/table if they don't exist
    exec_sql(conn, f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
    exec_sql(conn, f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
          id BIGINT GENERATED ALWAYS AS IDENTITY,
          note STRING,
          created_at TIMESTAMP DEFAULT current_timestamp()
        )
    """)

def list_notes(conn, limit: int = 20):
    rows = exec_sql(conn, f"""
        SELECT id, note, created_at
        FROM {TABLE}
        ORDER BY created_at DESC
        LIMIT {limit}
    """)
    return rows or []

def add_note(conn, note: str):
    exec_sql(conn, f"INSERT INTO {TABLE} (note) VALUES (%(note)s)", {"note": note})

st.title("Databricks SQL + Streamlit (token via Databricks SDK)")

# Try to connect and initialize
try:
    conn = get_connection(WAREHOUSE_ID)
    init_objects(conn)
except Exception as e:
    st.error(f"Connection/initialization error: {e}")
    st.stop()

# UI: add a note
with st.form("add_note", clear_on_submit=True):
    st.write(f"Target table: {TABLE}")
    note = st.text_input("Note", placeholder="Hello, DBSQL 👋")
    submitted = st.form_submit_button("Save")
    if submitted:
        if note.strip():
            try:
                add_note(conn, note.strip())
                st.success("Saved.")
            except Exception as e:
                st.error(f"Insert failed: {e}")
        else:
            st.warning("Please enter a note.")

st.divider()
st.write("Recent notes")
try:
    rows = list_notes(conn)
    if not rows:
        st.info("No notes yet. Add one above.")
    else:
        df = pd.DataFrame(rows, columns=["id", "note", "created_at"])
        st.dataframe(df, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Query failed: {e}")