import os
import time
import streamlit as st
from urllib.parse import quote
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from databricks import sdk

st.set_page_config(page_title="Streamlit + Lakebase (SDK token)", layout="centered")

# 1) Read Postgres params injected by the Databricks App Database resource
PGHOST = os.environ.get("PGHOST", "")
PGDATABASE = os.environ.get("PGDATABASE", "")
PGUSER = os.environ.get("PGUSER", "")
PGPORT = os.environ.get("PGPORT", "5432")
PGSSLMODE = os.environ.get("PGSSLMODE", "require")

# 2) Minimal validation
missing = [k for k, v in [("PGHOST", PGHOST), ("PGDATABASE", PGDATABASE), ("PGUSER", PGUSER)] if not v]
if missing:
    st.error(f"Missing required environment variables: {', '.join(missing)}")
    st.stop()

# 3) Initialize Databricks SDK (uses app service principal in Apps)
w = sdk.WorkspaceClient()  # SDK manages OAuth tokens and caching under the hood

# 4) Create engine with a connect hook that injects a fresh OAuth token as the "password"
def db_url_without_password() -> str:
    return f"postgresql+psycopg://{PGUSER}:@{PGHOST}:{PGPORT}/{PGDATABASE}"

@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    engine = create_engine(
        db_url_without_password(),
        pool_pre_ping=True,
        connect_args={"sslmode": PGSSLMODE},
    )

    # Refresh every ~15 minutes (token lifetime). Adjust if needed.
    token_cache = {"value": None, "ts": 0}
    refresh_secs = 15 * 60

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        now = time.time()
        if token_cache["value"] is None or (now - token_cache["ts"]) > refresh_secs:
            # Obtain a fresh OAuth access token with the SDK
            token_cache["value"] = w.config.oauth_token().access_token
            token_cache["ts"] = now
        cparams["password"] = token_cache["value"]

    return engine

def init_db(engine: Engine):
    ddl = """
    CREATE SCHEMA IF NOT EXISTS app;

    CREATE TABLE IF NOT EXISTS app.notes (
      id BIGSERIAL PRIMARY KEY,
      note TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

def list_notes(engine: Engine, limit: int = 20):
    sql = """
    SELECT id, note, created_at
    FROM app.notes
    ORDER BY created_at DESC
    LIMIT :limit
    """
    with engine.begin() as conn:
        return conn.execute(text(sql), {"limit": limit}).mappings().all()

def add_note(engine: Engine, note: str):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.notes (note) VALUES (:n)"), {"n": note})

st.title("Lakebase + Streamlit (token via Databricks SDK)")

# Connect and bootstrap
try:
    engine = get_engine()
    init_db(engine)
except Exception as e:
    st.error(f"Connection/initialization error: {e}")
    st.stop()

# UI
with st.form("add_note", clear_on_submit=True):
    st.write("Add a note")
    note = st.text_input("Note", placeholder="Hello, Lakebase 👋")
    submitted = st.form_submit_button("Save")
    if submitted:
        if note.strip():
            try:
                add_note(engine, note.strip())
                st.success("Saved.")
            except Exception as e:
                st.error(f"Insert failed: {e}")
        else:
            st.warning("Please enter a note.")

st.divider()
st.write("Recent notes")
try:
    rows = list_notes(engine)
    if not rows:
        st.info("No notes yet. Add one above.")
    else:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Query failed: {e}")