# Demo 2: Support Tickets with Lakebase

## Workshop User Guide

This guide walks you through building and deploying a support ticket application with Row-Level Security using Databricks Lakebase.

---

## What You Will Build

A Dash application that:
- Submits support tickets with priority and assignee
- Displays tickets in a kanban board (Open, In Progress, Resolved, Closed)
- Updates ticket status in real-time
- Enforces Row-Level Security so users only see their assigned tickets

**Estimated Time**: 20-25 minutes

**Key Concepts**:
- Databricks Lakebase (managed PostgreSQL)
- Row-Level Security (RLS)
- On-Behalf-Of User Authorization
- CRUD operations with PostgreSQL

---

## Prerequisites

Before starting, ensure:
- **On-Behalf-Of User Authorization** is enabled in your workspace (Admin Settings > Previews)
- You have access to a Databricks workspace with Apps enabled

---

## Step 1: Run the Setup Notebook

The database must be created before deploying the app.

1. Open `setup-lakebase.ipynb` in your Databricks workspace
2. Run all cells (takes 3-5 minutes)

The notebook will:
- Create a Lakebase instance (`support-tickets-lakebase`)
- Create a Unity Catalog catalog
- Create the `support_tickets` table
- Enable Row-Level Security
- Seed sample tickets for workspace users
- Create a performance index

### What is Row-Level Security?

RLS is a PostgreSQL feature that filters data at the database level:

```sql
-- Enable RLS on the table
ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;

-- Force RLS to apply to table owner (owners bypass RLS by default)
ALTER TABLE public.support_tickets FORCE ROW LEVEL SECURITY;

-- Create policy for user isolation
CREATE POLICY user_isolation_policy ON public.support_tickets
FOR ALL
USING (LOWER(assigned_to) = LOWER(current_user))
```

This policy ensures users only see rows where `assigned_to` matches their email - no application code needed.

**Note**: `ENABLE` turns on RLS for regular users, but table owners bypass it by default. `FORCE` ensures RLS applies to everyone, including the table owner. You can toggle `BYPASSRLS` in the Lakebase database roles settings to test with/without RLS as the owner.

---

## Step 2: Create the App

1. Navigate to **Compute** > **Apps**
2. Click **New** > **Create app**
3. Select **Create a custom app**
4. Fill in the details:
   - **Name**: `demo-2-support-tickets-dash`
   - **Description**: "Support ticket system with Lakebase"
5. Click **Next: Configure**

---

## Step 3: Configure App Resources

### Add Database Resource

1. Under **App resources**, click **Add resource**
2. Select **Database**
3. Configure:
   - **Instance**: `support-tickets-lakebase`
   - **Database**: `databricks_postgres`

This injects connection parameters as environment variables (PGHOST, PGDATABASE, etc.). No passwords are stored - authentication uses OAuth tokens.

### User Authorization

With On-Behalf-Of authorization enabled, the app receives the user's OAuth token via the `X-Forwarded-Access-Token` header. This allows the app to connect to the database as the actual user, enabling RLS.

**How it works:**

```
Without On-Behalf-Of:
User A → App (Service Principal) → Database → Sees ALL rows

With On-Behalf-Of:
User A → App (User A's Token) → Database → Sees only User A's rows
```

### Compute Size

Leave at **Medium**. Scale up for production apps with heavy database operations.

---

## Step 4: Deploy the App

1. Click **Create app**
2. Wait for provisioning (2-3 minutes)

---

## Step 5: Upload Source Code

1. Click **Sync from Git** or **Upload files**
2. Configure:
   - Path: `apps/demo2_support_tickets_dash`
   - Branch: `main`
3. Click **Deploy**

---

## Step 6: Use the Application

### Submit a Ticket

1. Open the app URL
2. On the **Submit Ticket** page, fill in:
   - Title
   - Description
   - Your email
   - Priority
   - Assignee (select from dropdown)
3. Click **Submit Ticket**

### View Your Tickets

1. Click **My Tickets** in the navigation
2. View tickets organized by status in kanban columns
3. Note: You only see tickets assigned to you (RLS in action)

### Update Ticket Status

1. Click **Update** on any ticket
2. Select a new status
3. Click **Update**

The board refreshes immediately with the new status.

---

## Understanding the Code

### Database Connection with User Credentials

The app injects user credentials into each database connection:

```python
@event.listens_for(engine, "do_connect")
def provide_token(dialect, conn_rec, cargs, cparams):
    user_email = request.headers.get('X-Forwarded-Email')
    user_token = request.headers.get('X-Forwarded-Access-Token')
    if user_email and user_token:
        cparams["user"] = user_email
        cparams["password"] = user_token
```

### Simple Query (RLS Handles Filtering)

No WHERE clause needed - PostgreSQL filters automatically:

```python
def get_tickets(engine):
    sql = "SELECT * FROM public.support_tickets ORDER BY created_at DESC"
    with engine.begin() as conn:
        result = conn.execute(text(sql)).mappings().all()
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Database not configured" | Ensure setup notebook was run and database resource is added |
| Users see no tickets | Verify On-Behalf-Of authorization is enabled in workspace |
| All users see all tickets | RLS not enabled; re-run setup notebook |
| Connection errors | Check that Lakebase instance is running (not stopped) |

---

## FAQ

**What if On-Behalf-Of authorization isn't enabled?**
The app connects as a Service Principal, which won't match any `assigned_to` values. Users will see no tickets.

**Can I use RLS with Delta Tables?**
Delta Tables use row filters and column masks in Unity Catalog - similar concept, different implementation.

**How do I debug RLS issues?**
Check the app logs for the PostgreSQL `current_user` value. It should be the user's email, not a UUID.

**How does performance scale?**
Lakebase uses the index on `assigned_to` for efficient RLS. Scale the instance capacity for high-traffic apps.

---

## Next Steps

Try these exercises:
1. Create a new ticket and assign it to yourself
2. Update ticket status through the workflow
3. (If possible) Log in as a different user to see RLS in action
4. Explore the setup notebook to understand the RLS policy

---

## Summary

You have deployed a multi-user application that:
- Uses Databricks Lakebase for transactional data
- Enforces Row-Level Security at the database level
- Propagates user identity via On-Behalf-Of authorization
- Demonstrates production patterns for OLTP workloads
