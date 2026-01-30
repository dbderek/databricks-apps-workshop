# Support Ticket System with Databricks Lakebase

A Dash-based support ticket management system that demonstrates OLTP patterns using Databricks Lakebase for transactional workloads.

## Features

- 🎫 **Create Tickets**: Submit new support tickets with title, description, email, and priority
- 📋 **View & Filter**: Browse all tickets with status-based filtering
- 🔄 **Update Status**: Change ticket status through an intuitive modal interface
- ⚡ **Real-time Updates**: Auto-refresh every 5 seconds to show latest tickets
- 🎨 **Modern UI**: Bootstrap-styled interface with color-coded status and priority badges
- 🔒 **Secure**: Uses OAuth token refresh for Lakebase authentication

## Configuration

The app uses environment variables for Lakebase connection (automatically injected by Databricks Apps):

- `PGHOST`: PostgreSQL host
- `PGDATABASE`: Database name
- `PGUSER`: Database user
- `PGPORT`: Database port (default: 5432)
- `PGSSLMODE`: SSL mode (default: require)
- `LAKEBASE_SCHEMA`: Schema name (default: `app`)
- `LAKEBASE_TABLE`: Table name (default: `support_tickets`)

## Database Schema

The app automatically creates the following table:

```sql
CREATE TABLE app.support_tickets (
  id BIGSERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  customer_email VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'open',
  priority VARCHAR(20) NOT NULL DEFAULT 'medium',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set up Lakebase connection environment variables
export PGHOST=your-lakebase-host
export PGDATABASE=your-database
export PGUSER=your-user

# Run the app
python app.py
```

## Deploying to Databricks Apps

1. Create a Databricks Lakebase instance
2. Configure the app.yml to reference your Lakebase instance as a database resource
3. Deploy using Databricks Apps CLI or UI
4. The app will automatically connect and initialize the schema

## Usage

### Creating Tickets
1. Fill in the ticket details in the left panel
2. Select priority level
3. Click "Create Ticket"

### Managing Tickets
1. View all tickets in the right panel
2. Filter by status using the dropdown
3. Click "Update Status" on any ticket to change its state

### Status Workflow
- 🔴 **Open**: New tickets
- 🟡 **In Progress**: Being worked on
- 🟢 **Resolved**: Issue fixed
- ⚫ **Closed**: Ticket completed

## Workshop Notes

This app demonstrates:
- CRUD operations with Lakebase (PostgreSQL-compatible)
- OAuth token management for secure database access
- Transactional workload patterns (reads and writes)
- Real-time UI updates with Dash callbacks
- Production-ready error handling and connection pooling
- Auto-schema initialization
