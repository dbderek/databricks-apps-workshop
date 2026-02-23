# Demo 3: Databricks SQL + Dash with MCP

## Workshop User Guide

This guide walks you through building and deploying a Dash application with direct Databricks SQL integration, including AI-assisted development using the Model Context Protocol (MCP).

---

## What You Will Build

A Dash application that:
- Connects directly to Databricks SQL using the SQL Connector
- Creates and manages tables in Unity Catalog
- Provides a simple note-taking interface with auto-generated IDs and timestamps
- Uses AI tools with MCP to modify both application code and database schemas

**Estimated Time**: 25-30 minutes

**Key Concepts**:
- Databricks SQL Connector
- Unity Catalog three-level namespace (catalog.schema.table)
- Delta Lake features (identity columns, default timestamps)
- Databricks Asset Bundles (DABs)
- Model Context Protocol (MCP) for AI-assisted development

---

## Prerequisites

Before starting, ensure you have:
- Access to a Databricks workspace with Apps enabled
- A SQL Warehouse (Serverless recommended for quick startup)
- Unity Catalog access with permissions to CREATE SCHEMA and CREATE TABLE
- Git repository configured with the workshop code
- (Optional) An AI tool with MCP support (GitHub Copilot, Cursor, Claude Desktop, etc.)

---

## Step 1: Configure Your Environment

### 1a. Update databricks.yml

In the root of the repository, update `databricks.yml` with your workspace URL and SQL Warehouse ID:

```yaml
variables:
  dbsql_serverless_warehouse_id:
    description: The Databricks SQL Serverless Warehouse ID to use for this bundle.

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://<your-databricks-instance>
    variables:
      dbsql_serverless_warehouse_id: "<your-dev-dbsql-serverless-warehouse-id>"
```

Replace:
- `<your-databricks-instance>` with your actual workspace URL (e.g., `myworkspace.cloud.databricks.com`)
- `<your-dev-dbsql-serverless-warehouse-id>` with your SQL Warehouse ID (found in **SQL Warehouses** page)

### 1b. Update DAB Resources and App Configuration

The app configuration is split across two files:

**`dab/resources/apps.yml`** — Defines the DAB app resource, API scopes, and warehouse binding:

```yaml
resources:
  apps:
    dash-dbsql:
      name: "dash-dbsql"
      source_code_path: ../../apps/demo3_dash_dbsql
      description: "A Dash app for exploring Databricks SQL"
      user_api_scopes:
        - sql
        - catalog.tables:read
        - catalog.schemas:read
        - catalog.catalogs:read
      resources:
        - name: "sql-warehouse"
          sql_warehouse:
            id: ${var.dbsql_serverless_warehouse_id}
            permission: "CAN_USE"
```

The warehouse ID here references the `dbsql_serverless_warehouse_id` variable you set in `databricks.yml`. You typically don't need to change this file unless you want to rename the app or modify API scopes.

**`apps/demo3_dash_dbsql/app.yml`** — Defines the app's runtime command and environment variables:

```yaml
command: [
  "python", "app.py"
]
env:
  - name: SQL_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: DATABRICKS_CATALOG
    value: startups_catalog
  - name: DATABRICKS_SCHEMA
    value: dw_apps
```

Update the environment variables:
- `DATABRICKS_CATALOG` — Replace `startups_catalog` with your Unity Catalog name (e.g., `main`)
- `DATABRICKS_SCHEMA` — Replace `dw_apps` with your schema name (e.g., `default`)

> **Note:** The `SQL_WAREHOUSE_ID` env var uses `valueFrom: sql-warehouse`, which automatically resolves the warehouse ID from the DAB resource named `sql-warehouse` defined in `dab/resources/apps.yml`. You don't need to hardcode it here.

### 1c. Setup MCP Configuration (Optional - for AI-Assisted Development)

If you want to use AI-assisted development features, create `.vscode/mcp.json` in the project root:

```json
{
  "servers": {
    "databricks-sql": {
      "command": "uvx",
      "args": ["databricks-mcp-server"],
      "env": {
        "DATABRICKS_HOST": "<DATABRICKS_HOST>",
        "DATABRICKS_TOKEN": "<PAT_TOKEN>"
      }
    }
  }
}
```

Replace:
- `<DATABRICKS_HOST>` with your workspace URL (e.g., `your-workspace.cloud.databricks.com`)
- `<PAT_TOKEN>` with a personal access token from User Settings > Developer > Access Tokens

**Note**: MCP setup is optional. You can complete the core demo without it. The MCP section enables the AI-assisted development workflow shown in Step 5.

---

## Step 2: Deploy with Databricks Asset Bundles

Databricks Asset Bundles (DABs) provide Infrastructure-as-Code for Databricks resources.

### 2a. Initialize the Bundle

```bash
databricks bundle init
```

This sets up the initial configuration and validates your CLI connection.

### 2b. Validate the Bundle

```bash
databricks bundle validate -t dev
```

This checks that all configuration files are correct and you have the necessary permissions.

**What's being validated:**
- App configuration
- SQL Warehouse resource binding
- Environment variables
- Permissions

### 2c. Deploy the Bundle

```bash
./deploy_app_bundle.sh dev
```

This script wraps the `databricks bundle deploy` command and handles the deployment process.

**What happens during deployment (2-3 minutes):**
- Creates the app as a Databricks resource
- Configures resources (SQL Warehouse)
- Syncs your code to the workspace
- Starts the application

Once deployment completes, note the app URL provided in the output.

---

## Step 3: Use the Application

### 3a. Open the App

Navigate to the app URL from the deployment output (also available in Compute > Apps).

### 3b. Configure Connection Settings

You'll see three input fields:
- **SQL Warehouse ID**: Pre-populated from your environment variable
- **Catalog**: Your Unity Catalog name (e.g., `main`)
- **Schema**: Your schema name (e.g., `default`)

Unity Catalog uses a three-level namespace: **catalog.schema.table**. This provides fine-grained access control and organization.

### 3c. Test Connection & Initialize

1. Click **Test Connection & Initialize**

This will:
- Resolve the warehouse hostname and HTTP path using the Databricks SDK
- Establish a connection with OAuth authentication
- Create the schema if it doesn't exist
- Create the `notes` table with Delta Lake features

**Success message**: "Successfully connected! Table 'catalog.schema.notes' ready."

**The table schema:**
```sql
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.notes (
  id BIGINT GENERATED ALWAYS AS IDENTITY,
  note STRING NOT NULL,
  created_by STRING,
  created_at TIMESTAMP DEFAULT current_timestamp()
)
```

**Delta Lake features used:**
- `GENERATED ALWAYS AS IDENTITY`: Auto-incrementing IDs
- `DEFAULT current_timestamp()`: Automatic timestamps

### 3d. Add a Note

1. Type a note in the text field (e.g., "My first workshop note!")
2. Click **Save Note**

The app automatically captures your email address using the Databricks SDK and inserts the note with a parameterized query for SQL injection protection.

**Success message**: "Saved!" in green

### 3e. View Notes

The table displays all your notes with columns:
- **id**: Auto-generated identity
- **note**: The text you entered
- **created_by**: Your email address (automatically captured)
- **created_at**: Timestamp of creation

Click **Refresh** to manually update the table with the latest data.

---

## Step 4: AI-Assisted Development with MCP (Optional)

**Note**: This step requires MCP configuration from Step 1c. If you skipped that setup, you can continue without this section.

This section demonstrates how to use AI tools with the Databricks SQL MCP server to modify both the application and database schema simultaneously.

### Scenario: Adding a Due Date Feature

Let's add a due date field to track when notes should be completed.

### 4a. Open Your AI Tool

Open VS Code with GitHub Copilot (or Cursor, Claude Desktop, etc.) with MCP configured.

### 4b. Issue the AI Prompt

Open your AI chat interface and enter:

```
I just deployed my app using databricks asset bundles. After deploying it, 
I realized that I need a column to track due date of the note. In order to 
do this, we need to update the app interface and the schema in the destination 
databricks table. Can you make these changes? The table is stored at 
[catalog.schema.notes]. Utilize the databricks-sql MCP server to make the 
schema changes.
```

Replace `[catalog.schema.notes]` with your actual catalog and schema names.

### 4c. Watch the AI Work

The AI should:

1. **Query the current schema** using MCP tools to understand the table structure
2. **Execute ALTER TABLE** to add the `due_date` column:
   ```sql
   ALTER TABLE catalog.schema.notes ADD COLUMN due_date DATE
   ```
3. **Update app.py** to add:
   - A date picker widget in the UI
   - Updated `insert_note` function to accept `due_date` parameter
   - Modified callback to pass the date value
   - Updated display logic to show the new column

### 4d. Review the Changes

**Check app.py changes:**
- New `dcc.DatePickerSingle` widget added to the form
- `insert_note` function signature updated
- Callback function updated to handle the date input
- Table display updated to show the due date column

The AI coordinated changes across multiple parts of the codebase, understanding the architecture of Dash callbacks, database layer, and UI components.

### 4e. Redeploy and Test

```bash
databricks bundle destroy -t dev
./deploy_app_bundle.sh dev
```

**Why destroy first?**
This ensures a clean deployment with no leftover state. Asset Bundles provide reproducible deployments every time.

**Once redeployed:**

1. Navigate to the app URL
2. Test the connection (schema now includes `due_date`)
3. Add a note with a due date
4. Verify the table displays the new column

The due date feature is now fully functional with both database schema and application code updated through AI assistance.

---

## Understanding the Code

### Authentication Pattern

```python
def get_oauth_token():
    """Get access token from request headers."""
    token = request.headers.get('X-Forwarded-Access-Token')
    if not token:
        raise ValueError("X-Forwarded-Access-Token header not found")
    return token
```

Databricks Apps automatically inject OAuth tokens for every request. No credential storage or management needed.

### Dynamic Warehouse Resolution

```python
def resolve_endpoint(warehouse_id: str):
    w = get_workspace_client()
    warehouse = w.warehouses.get(warehouse_id)
    host = warehouse.odbc_params.hostname
    http_path = warehouse.odbc_params.path
    return host, http_path
```

Instead of hardcoding connection strings, the app dynamically resolves the warehouse endpoint using the SDK. This works across different workspace environments.

### Parameterized Queries

```python
def insert_note(conn, table_name, note: str, created_by: str):
    exec_sql(conn, 
        f"INSERT INTO {table_name} (note, created_by) VALUES (%(note)s, %(created_by)s)",
        {"note": note, "created_by": created_by}
    )
```

Using parameterized queries with `%(name)s` syntax prevents SQL injection attacks by properly escaping user input.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "X-Forwarded-Access-Token header not found" | Ensure app is deployed via Databricks Apps, not running locally |
| "Warehouse not found" | Verify warehouse ID in databricks.yml and app.yml match an accessible warehouse |
| "Permission denied on catalog/schema" | Check Unity Catalog permissions; ensure CREATE SCHEMA and CREATE TABLE grants |
| Asset Bundle validation fails | Check YAML syntax; verify workspace URL and credentials |
| MCP server connection fails | Verify PAT token is valid; check workspace URL in mcp.json |
| AI doesn't use MCP tools | Ensure MCP server is properly configured; explicitly mention "use the databricks-sql MCP server" in prompt |

---

## FAQ

**Why use Databricks SQL Connector instead of SQLAlchemy?**
The Databricks SQL Connector is purpose-built for Databricks. It handles Unity Catalog namespacing, provides better error messages, and is optimized for SQL Warehouse performance.

**Can I use this pattern with compute clusters instead of SQL Warehouses?**
For SQL operations, SQL Warehouses are recommended. They're optimized for query workloads, support auto-scaling, and have predictable performance.

**How does the app handle concurrent users?**
Each request gets its own database connection with proper isolation. SQL Warehouses handle concurrency with automatic scaling.

**What about the MCP server - is it secure?**
Yes. The MCP server uses your personal access token and respects Unity Catalog permissions. The AI can only query and modify tables you have access to.

**Can I use MCP with other AI tools besides Copilot?**
Absolutely. MCP is an open standard. Cursor, Claude Desktop, and other tools support it with similar configuration.

**What is the difference between this and Lakebase in Demo 2?**
Delta Tables (used here) are excellent for moderate write loads with analytical needs. Lakebase (PostgreSQL) is better for very high-frequency OLTP workloads requiring sub-millisecond latencies.

---

## Next Steps

Try these exercises:
1. Add more notes with different content
2. (Advanced) Use the MCP server with your AI tool to add another field (e.g., priority or category)
3. Modify the table to add filtering or sorting capabilities
4. Explore the code in `app.py` to understand the Dash callback patterns
5. Try querying the Unity Catalog table directly using SQL to see the data

---

## Summary

You have deployed a Databricks application that:
- Uses Databricks SQL Connector for direct Unity Catalog integration
- Leverages Delta Lake features for transactional operations
- Employs Databricks Asset Bundles for repeatable, infrastructure-as-code deployments
- (Optional) Demonstrates AI-assisted development with MCP for coordinated code and schema changes

This pattern is suitable for applications requiring moderate write loads with the benefits of Unity Catalog governance, Delta Lake ACID transactions, and seamless integration with the Databricks analytics platform.
