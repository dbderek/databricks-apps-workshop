# Databricks SQL Notes App with Dash

A modern Dash application demonstrating direct integration with Databricks SQL using the Databricks SQL Connector. Features a clean note-taking interface with real-time data operations powered by Unity Catalog.

## Features

- **Direct DBSQL Integration**: Uses Databricks SQL Connector for efficient query execution
- **Unity Catalog**: Works with Unity Catalog's three-level namespace (catalog.schema.table)
- **User Authentication**: Leverages OAuth token from request headers for secure access
- **Auto Table Creation**: Automatically creates and initializes Delta tables with proper schema
- **Real-time Operations**: Insert and query notes with immediate refresh
- **User Tracking**: Automatically captures and displays who created each note
- **Modern UI**: Clean, responsive design with Databricks brand colors
- **Connection Testing**: Built-in connection testing and validation

## How It Works

1. **Configure**: Enter SQL Warehouse ID, catalog, and schema
2. **Connect**: Test connection and auto-create the notes table
3. **Create**: Add notes with automatic user attribution
4. **View**: Browse recent notes in a formatted data table
5. **Refresh**: Manually refresh or auto-update after saving

## Architecture

```
demo3_dash_dbsql/
├── app.py              # Main Dash application
├── app.yml             # Databricks Apps configuration
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Technical Highlights

### Databricks SQL Integration

The app demonstrates best practices for DBSQL connections:

- **OAuth Token Flow**: Extracts `X-Forwarded-Access-Token` from request headers
- **Warehouse Resolution**: Uses Databricks SDK to resolve warehouse ODBC parameters
- **Parameterized Queries**: Uses parameter binding for secure SQL execution
- **Connection Management**: Properly handles connection lifecycle

### Delta Table Features

The notes table uses Delta Lake capabilities:

```sql
CREATE TABLE {catalog}.{schema}.notes (
  id BIGINT GENERATED ALWAYS AS IDENTITY,
  note STRING,
  created_by STRING,
  created_at TIMESTAMP DEFAULT current_timestamp()
) TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')
```

Key features:
- **Identity Column**: Auto-incrementing ID for each note
- **Default Timestamp**: Automatic timestamp on creation
- **Column Defaults**: Uses Delta Lake column defaults feature

## Configuration

### Environment Variables

Set these via Databricks Apps resource configuration:

| Variable | Source | Description | Default |
|----------|--------|-------------|---------|
| `SQL_WAREHOUSE_ID` | SQL Warehouse resource | Warehouse ID for SQL execution | (required) |
| `DATABRICKS_CATALOG` | Manual or resource | Unity Catalog name | `main` |
| `DATABRICKS_SCHEMA` | Manual or resource | Schema name | `default` |

### App Resources

When creating the Databricks App, add:

1. **SQL Warehouse**: Select a SQL Warehouse for query execution

The warehouse ID is automatically injected as `SQL_WAREHOUSE_ID` environment variable.

## Prerequisites

- Databricks workspace with Apps enabled
- SQL Warehouse (Serverless or Pro recommended)
- Unity Catalog access with CREATE SCHEMA and CREATE TABLE permissions
- Catalog and schema where you have write access (or use defaults)

## Deploying to Databricks Apps

### Using Databricks Asset Bundles (Recommended)

This app is part of a workshop bundle. From the repository root:

1. Configure `databricks.yml` with your workspace URL and warehouse ID
2. Validate: `databricks bundle validate -t dev`
3. Deploy: `./deploy_app_bundle.sh dev`

See the [Workshop User Guide](WORKSHOP_USER_GUIDE.md) for detailed step-by-step instructions.

### Manual Deployment

1. Create a new Databricks App (custom app)
2. Add a **SQL Warehouse** resource
3. (Optional) Set custom catalog/schema in environment variables
4. Sync code from Git or upload files
5. Deploy the app

Authentication is handled automatically via OAuth tokens - no credentials needed in code.

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set Databricks credentials
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=your-token
export SQL_WAREHOUSE_ID=your-warehouse-id
export DATABRICKS_CATALOG=main
export DATABRICKS_SCHEMA=default

# Run the app
python app.py
```

Note: Local development requires proper Databricks authentication setup.

## Code Architecture

### Helper Functions

- `get_workspace_client()`: Creates SDK client with OAuth token
- `resolve_endpoint(warehouse_id)`: Resolves warehouse hostname and HTTP path
- `get_oauth_token()`: Extracts access token from request headers
- `get_current_user()`: Retrieves current user's email
- `get_connection(warehouse_id)`: Creates DBSQL connection
- `exec_sql(conn, statement, params)`: Executes parameterized SQL
- `ensure_table(conn, catalog, schema)`: Creates schema and table if needed
- `list_notes(conn, table_name, limit)`: Queries recent notes
- `insert_note(conn, table_name, note, created_by)`: Inserts new note

### Dash Callbacks

1. **Connection Test**: Validates warehouse connection and creates table
2. **Save Note**: Inserts note with user tracking and triggers refresh
3. **Refresh Table**: Loads and displays recent notes

## Usage Tips

### Customizing Catalog/Schema

The app defaults to `main.default` but you can:

1. Set environment variables before deployment
2. Change values in the UI connection settings
3. Use any catalog/schema where you have permissions

### Warehouse Selection

- **Serverless**: Fastest startup, auto-scaling
- **Pro**: Good for moderate workloads
- **Classic**: Legacy option

All warehouse types work with this app.

### Troubleshooting

**"X-Forwarded-Access-Token header not found"**
- Ensure app is deployed in Databricks Apps (not running standalone)
- Token is automatically injected by Databricks Apps platform

**"Permission denied on catalog/schema"**
- Verify you have CREATE and SELECT permissions
- Try using a catalog/schema where you have ownership

**"Warehouse not found"**
- Check the warehouse ID is correct
- Verify warehouse is running and accessible

## Security Notes

- **User Authentication**: OAuth tokens ensure only authenticated users can access
- **User Attribution**: All notes track who created them
- **No Stored Credentials**: Tokens are passed per-request, never stored
- **SQL Injection Protection**: Uses parameterized queries

## Performance Considerations

- Queries are limited to 20 most recent notes by default
- Connection pooling is not used (stateless per-request pattern)
- Warehouse auto-scaling handles concurrent users
- Delta Lake provides transactional guarantees

## Extension Ideas

- Add search/filter functionality
- Implement note editing and deletion
- Add categories or tags
- Export notes to CSV/JSON
- Add pagination for large note lists
- Implement collaborative features (comments, likes)
- Add rich text formatting for notes
