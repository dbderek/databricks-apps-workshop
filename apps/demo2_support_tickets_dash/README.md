# Support Ticket System with Databricks Lakebase

A Dash-based support ticket management system featuring a kanban board interface and Row-Level Security (RLS) using Databricks Lakebase (PostgreSQL).

## Features

- **Submit Tickets**: Create support tickets with title, description, priority, and assignee
- **Kanban Board**: View tickets in columns by status (Open, In Progress, Resolved, Closed)
- **Status Updates**: Change ticket status through an intuitive modal interface
- **Row-Level Security**: Users only see tickets assigned to them (enforced at database level)
- **Real-time Updates**: Auto-refresh every 30 seconds
- **Modern UI**: Clean, responsive design with Helvetica font and blue accent colors

## Prerequisites

Before deploying this app, you must run the setup notebook to create the Lakebase instance and seed data:

1. Open `setup-lakebase.ipynb` in a Databricks notebook
2. Run all cells to:
   - Create the Lakebase instance and catalog
   - Create the `support_tickets` table with proper schema
   - Enable Row-Level Security (RLS)
   - Seed sample tickets for all workspace users

## Configuration

The app uses environment variables for Lakebase connection (automatically injected by Databricks Apps when you configure a database resource):

| Variable | Description | Default |
|----------|-------------|---------|
| `PGHOST` | PostgreSQL host | (required) |
| `PGDATABASE` | Database name | (required) |
| `PGUSER` | Database user | (required) |
| `PGPORT` | Database port | `5432` |
| `PGSSLMODE` | SSL mode | `require` |
| `LAKEBASE_SCHEMA` | Schema name | `public` |
| `LAKEBASE_TABLE` | Table name | `support_tickets` |

## Database Schema

The setup notebook creates the following table:

```sql
CREATE TABLE public.support_tickets (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    assigned_to VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Row-Level Security ensures users only see tickets where `assigned_to` matches their email (case-insensitive).

**RLS Configuration**:
- `ENABLE ROW LEVEL SECURITY` - Activates RLS for regular users
- `FORCE ROW LEVEL SECURITY` - Ensures RLS applies to table owner too (owners bypass by default)

Table owners can toggle `BYPASSRLS` in the Lakebase database roles settings to test with/without RLS.

## Deploying to Databricks Apps

1. Run `setup-lakebase.ipynb` to create the Lakebase instance and table
2. Create a new Databricks App
3. Add a database resource pointing to your Lakebase instance
4. Enable "On behalf of user authorization" in app settings (required for RLS)
5. Deploy the app

## App Structure

```
demo2_support_tickets_dash/
├── app.py                  # Main Dash application
├── app.yml                 # Databricks Apps configuration
├── requirements.txt        # Python dependencies
├── setup-lakebase.ipynb    # Database setup notebook
├── README.md               # This file
└── WORKSHOP_USER_GUIDE.md  # Step-by-step workshop guide
```

## Usage

### Submitting Tickets

1. Navigate to "Submit Ticket" page
2. Fill in ticket details (title, description, email, priority)
3. Select an assignee from the dropdown
4. Click "Submit Ticket"

### Managing Tickets

1. Navigate to "My Tickets" page
2. View your assigned tickets organized by status
3. Click "Update" on any ticket to change its status
4. Select new status and confirm

### Status Workflow

| Status | Description |
|--------|-------------|
| Open | New tickets awaiting action |
| In Progress | Being actively worked on |
| Resolved | Issue has been fixed |
| Closed | Ticket completed |

## Technical Notes

- Uses SQLAlchemy with NullPool for per-request database connections
- OAuth tokens injected via `X-Forwarded-Access-Token` header for RLS
- Dash callbacks handle all UI interactions
- Bootstrap (Flatly theme) for responsive styling
