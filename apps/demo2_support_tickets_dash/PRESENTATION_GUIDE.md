# Demo 2: Support Tickets with Lakebase

## Presentation Guide for Workshop Facilitators

This guide provides a complete talk track and step-by-step walkthrough for demonstrating the Support Tickets app with Databricks Lakebase in a hands-on workshop.

---

## Overview

| Aspect | Details |
|--------|---------|
| **Demo Duration** | 20-25 minutes |
| **App Framework** | Dash (Plotly) |
| **Key Databricks Features** | Lakebase (PostgreSQL), Row-Level Security, On-Behalf-Of User Authorization |
| **Use Case** | OLTP / Transactional Application with Data Governance |

### What This Demo Shows

- Building transactional (OLTP) applications with Databricks Lakebase
- Implementing Row-Level Security (RLS) at the database level
- Using "On-Behalf-Of User Authorization" for per-user data access
- CRUD operations with PostgreSQL via SQLAlchemy
- Production patterns for multi-user applications

---

## Pre-Workshop Setup

### Required Resources

1. **Lakebase Instance** created via the setup notebook
2. **Workspace Preview**: "On-Behalf-Of User Authorization" enabled (this takes time to propagate!)
3. **Workspace Users**: Add some users to populate the seeded data

### Critical: Enable On-Behalf-Of User Authorization

This must be done **before** the workshop:

1. Go to **Admin Settings** > **Workspace Settings** > **Previews**
2. Enable **Databricks Apps: On-behalf of user authorization**
3. Wait 15-30 minutes for propagation

> **Why This Matters**: Without this setting, the app connects to the database as a Service Principal, bypassing Row-Level Security. With it enabled, the `X-Forwarded-Access-Token` header is provided, allowing the app to connect as the actual user.

### Run the Setup Notebook

The `setup-lakebase.ipynb` notebook must be run before the demo:

1. Open the notebook in a Databricks workspace
2. Run all cells (takes 3-5 minutes)
3. The notebook will:
   - Create a Lakebase instance (`support-tickets-lakebase`)
   - Create a Unity Catalog catalog (`support_tickets_catalog`)
   - Create the `support_tickets` table in the `public` schema
   - Enable Row-Level Security on the table
   - Seed 2-3 tickets for every user in the workspace
   - Create an index on `assigned_to` for RLS query performance

---

## Step-by-Step Walkthrough

### Step 1: Show the Setup Notebook (3 min)

Before creating the app, briefly show the setup notebook:

> **Talk Track**: "Before we deploy the app, let's look at how we set up the database. This notebook creates a Lakebase instance - Databricks' managed PostgreSQL service - and configures Row-Level Security."

**Key cells to highlight:**

1. **Lakebase Instance Creation**
```python
instance = w.database.create_database_instance(
    name=LAKEBASE_INSTANCE_NAME,
    capacity=DatabaseInstanceCapacity.SMALL,
    stopped=False
)
```

> **Talk Track**: "Lakebase gives us a fully-managed PostgreSQL database. Unlike traditional OLAP workloads, this is designed for transactional use cases - low-latency reads and writes, like what you'd need for a web application."

2. **Row-Level Security Setup**
```python
cursor.execute(f"ALTER TABLE {PG_SCHEMA}.{PG_TABLE} ENABLE ROW LEVEL SECURITY")
cursor.execute(f"""
    CREATE POLICY user_isolation_policy ON {PG_SCHEMA}.{PG_TABLE}
    FOR ALL
    USING (assigned_to = current_user)
    WITH CHECK (assigned_to = current_user)
""")
```

> **Talk Track**: "Here's the key security feature: Row-Level Security. This policy says 'users can only see rows where the assigned_to column matches their username.' The magic is that `current_user` in PostgreSQL will be the actual end-user's email, thanks to the On-Behalf-Of authorization feature."

3. **Data Seeding**
```python
for user in users:
    for i in range(tickets_per_user):
        cursor.execute("""INSERT INTO support_tickets (...) VALUES (...)""")
```

> **Talk Track**: "We seed sample tickets for every user in the workspace. This means when you log in, you'll see your own tickets - not everyone else's. This simulates a real multi-tenant application."

### Step 2: Create the App (5 min)

1. Navigate to **Compute** > **Apps** in the Databricks workspace
2. Click **New** > **Create app**
3. Select **Create a custom app**

**Fill in the details:**
- **Name**: `demo-2-support-tickets-dash`
- **Description**: "A Databricks Apps hands-on workshop demo"

> **Talk Track**: "For this demo, we're using Dash - a Python framework from Plotly. It's great for building data-driven web applications. But the patterns we'll show work with any framework - Flask, FastAPI, Streamlit, or even Node.js."

4. Click **Next: Configure**

### Step 3: Configure App Resources (5 min)

#### 3a. Add Database Resource

1. Under **App resources**, click **Add resource**
2. Select **Database**
3. In the dropdown:
   - **Instance**: Select `support-tickets-lakebase`
   - **Database**: Select `databricks_postgres`

> **Talk Track**: "By adding the database as a resource, Databricks automatically injects connection parameters as environment variables: PGHOST, PGDATABASE, PGPORT, and PGUSER. The app doesn't need to know connection strings or manage credentials."

**Key Insight to Share:**
> "Notice we're not specifying a password anywhere. Authentication happens via OAuth tokens - the app's Service Principal token for initialization, and the user's token for actual queries. This is much more secure than traditional password-based database connections."

#### 3b. Configure User Authorization

1. Under **User authorization**, check the settings

> **Talk Track**: "This is the critical setting for Row-Level Security. With 'On-Behalf-Of User Authorization' enabled at the workspace level, the app receives the user's OAuth token in the `X-Forwarded-Access-Token` header. Our app uses this token to connect to the database as the actual user, not as the Service Principal."

**Diagram to draw or show:**
```
Without On-Behalf-Of:
User A → App (Service Principal) → Database → Sees ALL rows

With On-Behalf-Of:
User A → App (User A's Token) → Database → Sees only User A's rows
```

#### 3c. Compute Size

> **Talk Track**: "We'll leave compute at Medium, but for production apps with heavy database operations or many concurrent users, you might scale up."

### Step 4: Deploy the App (2 min)

1. Click **Create app**
2. The app will begin provisioning

> **Talk Track**: "Deployment takes a few minutes. In the meantime, let me explain how the authentication flow works in the code..."

**Code explanation during deployment:**

```python
@event.listens_for(engine, "do_connect")
def provide_token(dialect, conn_rec, cargs, cparams):
    # Try user token from forwarded headers (enables RLS)
    user_email = request.headers.get('X-Forwarded-Email')
    user_token = request.headers.get('X-Forwarded-Access-Token')
    if user_email and user_token:
        cparams["user"] = user_email
        cparams["password"] = user_token
        return
```

> **Talk Track**: "Every time SQLAlchemy opens a connection, we intercept it and inject the user's credentials. The email becomes the PostgreSQL username, and the OAuth token becomes the password. PostgreSQL validates this token against Databricks and sets `current_user` to the user's email - which is exactly what our RLS policy checks."

### Step 5: Sync Code and Deploy

1. Click **Sync from Git** or upload files
2. Configure the repository and path: `apps/demo2_support_tickets_dash`
3. Click **Deploy**

### Step 6: Demonstrate the App (7-10 min)

#### 6a. Show the Submit Ticket Page

> **Talk Track**: "This is the ticket intake form. Any user can submit a support ticket with a title, description, priority, and assignee. Notice the 'Assign To' dropdown - it's populated from existing users in the database."

**Point out:**
- Clean, modern UI with Helvetica font and blue accent color
- Form validation
- The logged-in user display in the navbar

#### 6b. Navigate to My Tickets (Kanban Board)

1. Click **My Tickets** in the navigation

> **Talk Track**: "This is where the magic happens. You're seeing a kanban board with tickets organized by status: Open, In Progress, Resolved, and Closed. But here's the key point - you're ONLY seeing tickets assigned to you."

2. Point out the user display showing the current user's email

> **Talk Track**: "The 'Logged in as' indicator shows your identity. The database query is a simple `SELECT * FROM support_tickets` - no WHERE clause for user filtering. Row-Level Security handles everything at the database level."

#### 6c. Demonstrate RLS (If multiple users available)

If possible, open the app in two browser sessions with different users:

> **Talk Track**: "Let me open another browser as a different user... Notice they see completely different tickets. Same app, same code, same query - but different data based on who's logged in. This is Row-Level Security in action."

#### 6d. Update a Ticket Status

1. Click **Update** on any ticket
2. Select a new status in the modal
3. Click **Update**

> **Talk Track**: "When we update a ticket, the change is immediately reflected on the board. This is a real database UPDATE operation, and it's also protected by RLS - users can only update tickets assigned to them."

#### 6e. Submit a New Ticket

1. Navigate back to **Submit Ticket**
2. Fill out the form
3. Click **Submit Ticket**

> **Talk Track**: "New tickets are inserted with an INSERT statement. The assignee dropdown lets you assign to yourself or another user. Once assigned, the assignee will see it in their My Tickets view."

---

## Key Talking Points

### Row-Level Security Benefits

> "RLS is a game-changer for multi-tenant applications. Traditional approaches require adding `WHERE user_id = ?` to every query, which is error-prone. With RLS, security is enforced at the database level - even if you forget a filter, users can't see data they shouldn't."

### Lakebase vs. Traditional PostgreSQL

> "Lakebase is managed PostgreSQL integrated with Unity Catalog. You get all the benefits of PostgreSQL - SQL standards, transactions, rich data types - but with Databricks' security model. OAuth tokens instead of passwords, catalog integration, and unified governance."

### On-Behalf-Of Authorization

> "The On-Behalf-Of pattern is essential for apps that need per-user data access. Without it, apps run as a Service Principal and all users see the same data. With it, each user's identity flows through to the database, enabling true multi-tenancy."

### When to Use Lakebase vs. Delta Tables

> "Use Lakebase for OLTP workloads: high-frequency reads and writes, low-latency requirements, transactional consistency. Use Delta Tables for analytics: large scans, aggregations, data lake patterns. Many applications use both - Lakebase for the operational database and Delta for analytics."

---

## Code Walkthrough (if time permits)

### Database Connection Pattern

```python
def get_engine():
    engine = create_engine(db_url, poolclass=NullPool, ...)
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        # Inject user credentials from headers
        user_email = request.headers.get('X-Forwarded-Email')
        user_token = request.headers.get('X-Forwarded-Access-Token')
        if user_email and user_token:
            cparams["user"] = user_email
            cparams["password"] = user_token
```

> "We use `NullPool` because each request might be a different user. The `do_connect` event lets us inject the right credentials per-request."

### Simple Query (RLS does the work)

```python
def get_tickets(engine):
    sql = "SELECT * FROM public.support_tickets ORDER BY created_at DESC"
    with engine.begin() as conn:
        result = conn.execute(text(sql)).mappings().all()
```

> "Notice there's no user filtering in the query. RLS handles it automatically."

---

## Common Questions & Answers

**Q: What happens if On-Behalf-Of authorization isn't enabled?**
A: The app connects as the Service Principal (a UUID), which doesn't match any `assigned_to` values. Users would see no tickets.

**Q: Can I use RLS with Delta Tables?**
A: Delta Tables use a different mechanism - row filters and column masks in Unity Catalog. The concepts are similar but implementation differs.

**Q: How do I debug RLS issues?**
A: Check the `X-Forwarded-Access-Token` header is being passed. In the app logs, we print the PostgreSQL `current_user` value - it should be the user's email, not a UUID.

**Q: What about service-to-service communication?**
A: For background jobs or admin tasks, the app can fall back to the Service Principal token. The code includes a fallback mechanism for when user headers aren't available.

**Q: How does performance scale?**
A: Lakebase handles RLS efficiently using the index on `assigned_to`. For high-traffic apps, you can scale the Lakebase instance capacity.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Database not configured" message | Ensure setup notebook was run and database resource is added |
| Users see no tickets | Check On-Behalf-Of authorization is enabled; verify `X-Forwarded-Access-Token` header |
| All users see all tickets | RLS not enabled; re-run setup notebook |
| Connection errors | Verify Lakebase instance is running (not stopped) |
| Modal pops up unexpectedly | This was fixed in the latest code - ensure code is synced |

---

## Workshop Participant Hands-On

After the demo, have participants:

1. Run the `setup-lakebase.ipynb` notebook in their environment
2. Create their own app following the configuration steps
3. Test the RLS by viewing tickets assigned to them
4. Create and update tickets
5. (Advanced) Modify the RLS policy to allow viewing all tickets but only updating own tickets

---

## Wrap-Up Talking Points

1. **Transactional Workloads**: "Lakebase brings true OLTP capabilities to the Databricks platform. Build web apps, APIs, and operational systems alongside your analytics."

2. **Security by Default**: "Row-Level Security eliminates a whole class of data exposure bugs. Security is enforced at the database level, not just application logic."

3. **Identity Propagation**: "On-Behalf-Of authorization means your app can act on behalf of the actual user, enabling per-user data access, audit trails, and compliance."

4. **Full Stack on Databricks**: "From data ingestion to analytics to serving - and now to operational applications. Databricks Apps completes the picture for end-to-end data platforms."
