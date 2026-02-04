# Demo 1: PDF Text Extraction with Vision AI

## Presentation Guide for Workshop Facilitators

This guide provides a complete talk track and step-by-step walkthrough for demonstrating the PDF Text Extraction app in a hands-on workshop.

---

## Overview

| Aspect | Details |
|--------|---------|
| **Demo Duration** | 15-20 minutes |
| **App Framework** | Streamlit |
| **Key Databricks Features** | Model Serving Endpoints, SQL Warehouse, OAuth Authentication |
| **Use Case** | Document AI / Intelligent Document Processing |

### What This Demo Shows

- How to build a Streamlit app that runs on Databricks Apps
- Integrating with Databricks Model Serving Endpoints (Vision AI)
- Using SQL Warehouse for data persistence
- Automatic OAuth token management via the Databricks SDK
- Production-ready patterns for AI-powered applications

---

## Pre-Workshop Setup

### Required Resources

1. **Model Serving Endpoint** with a vision-capable model (e.g., Claude, GPT-4V, or similar)
2. **SQL Warehouse** (Serverless recommended for quick startup)
3. Sample PDF documents for testing (a sample is included in the repo)

### Recommended Preparation

- Verify the serving endpoint is running and accessible
- Confirm the SQL Warehouse can start within reasonable time
- Have a sample PDF ready that demonstrates good extraction results

---

## Step-by-Step Walkthrough

### Step 1: Create the App (5 min)

1. Navigate to **Compute** > **Apps** in the Databricks workspace
2. Click **New** > **Create app**
3. Select **Create a custom app**

**Fill in the details:**
- **Name**: `demo-1-pdf-text-extraction`
- **Description**: "A Databricks Apps hands-on workshop demo"

> **Talk Track**: "Notice that Databricks Apps offers several scaffolding options for common use cases like chat agents, knowledge bots, and custom apps. For this demo, we're creating a custom Streamlit application that will use Vision AI to extract text from PDF documents."

4. Click **Next: Configure**

### Step 2: Configure App Resources (3 min)

1. Under **App resources**, click **Add resource**
2. Select **Serving endpoint**
   - Choose your vision-capable model endpoint
   - This provides the `DATABRICKS_SERVING_ENDPOINT` environment variable

> **Talk Track**: "By adding the serving endpoint as a resource, we're granting the app's Service Principal permission to call this endpoint. The app automatically receives the endpoint name as an environment variable, so we don't need to hardcode it."

3. Click **Add resource** again
4. Select **SQL Warehouse**
   - Choose your SQL Warehouse
   - This provides the `SQL_WAREHOUSE_ID` environment variable

> **Talk Track**: "Similarly, adding the SQL Warehouse as a resource grants the app permission to execute queries. This will be used for the 'Save to Delta Table' feature, allowing users to persist their extracted text for downstream analytics."

5. Leave compute size at **Medium** (mention larger sizes are available for memory-intensive apps)

### Step 3: Deploy the App (2 min)

1. Click **Create app**
2. The app will begin provisioning (takes 2-3 minutes)

> **Talk Track**: "While the app is deploying, let me explain what's happening behind the scenes. Databricks is spinning up a containerized environment with Python, Streamlit, and all our dependencies. It's also creating a Service Principal for the app and configuring OAuth credentials automatically."

**During deployment, explain the architecture:**
- The app runs in a managed container
- Authentication is handled automatically via the Databricks SDK
- Environment variables for resources are injected at runtime
- The app gets a unique URL accessible to workspace users

### Step 4: Upload Source Code (2 min)

Once the app is running, you'll see the default placeholder. Now sync your code:

1. Click **Sync from Git** or **Upload files**
2. If using Git:
   - Repository: `https://github.com/<your-repo>/databricks-apps-workshop`
   - Path: `apps/demo1_pdf_extractor_streamlit`
   - Branch: `main` (or your branch)

> **Talk Track**: "Databricks Apps supports both Git sync and direct file upload. For production apps, Git sync is recommended as it enables CI/CD workflows and version control."

3. Click **Deploy** to restart with the new code

### Step 5: Demonstrate the App (5-7 min)

Once the app loads:

#### 5a. Show the UI and Explain Components

> **Talk Track**: "This is a production-ready PDF extraction application built with Streamlit. Notice the clean UI - we have a file uploader, a customizable extraction prompt, and the model endpoint displayed in the header. This transparency helps users understand what AI model is processing their documents."

#### 5b. Upload a PDF

1. Click the file uploader and select a sample PDF
2. Point out the extraction prompt text area

> **Talk Track**: "The extraction prompt is customizable, which is powerful for different use cases. For invoices, you might want structured key-value pairs. For contracts, you might want section headers. The prompt gives users control over the output format."

#### 5c. Run Extraction

1. Click **Extract Text**
2. Watch the progress indicators

> **Talk Track**: "Behind the scenes, we're converting each PDF page to an image, then sending it to the Vision AI model via the serving endpoint. The progress bar shows real-time status. For larger documents, we automatically scale up the number of parallel workers."

#### 5d. Review Results

1. Show the side-by-side view (PDF preview on left, extracted text on right)
2. Navigate between pages using the dropdown

> **Talk Track**: "The side-by-side view lets users verify extraction quality page by page. This is essential for production use cases where accuracy matters."

#### 5e. Export Options

1. Show the three export buttons: CSV, Text, and Delta Table

> **Talk Track**: "Users can download results locally as CSV or plain text. But the real power is the 'Save to Delta Table' option - this persists the extracted text directly into Unity Catalog, making it available for downstream analytics, vector search indexing, or further AI processing."

2. (Optional) Click **Save to Delta Table** and show the modal

---

## Key Talking Points

### Security & Authentication

> "One of the biggest challenges in building AI applications is managing credentials securely. Notice that our code never handles tokens directly - the Databricks SDK automatically manages OAuth authentication. When the app calls the serving endpoint or SQL Warehouse, it uses the Service Principal's credentials, which are rotated automatically."

### Code Walkthrough (if time permits)

Point out these sections in `app.py`:

```python
# Authentication is automatic via the SDK
cfg = Config()
auth_result = cfg.authenticate()
```

> "This single line handles all authentication complexity - no API keys to manage, no token refresh logic to write."

```python
# Environment variables are injected by Databricks Apps
model_endpoint = os.getenv("DATABRICKS_SERVING_ENDPOINT")
```

> "The serving endpoint name comes from the resource we configured earlier. This decouples the code from specific endpoints, making it portable across environments."

### Production Readiness

> "This app includes production patterns you'd want in any AI application: error handling, progress indicators, session state management, and multiple export options. It's not just a demo - it's a template you can extend for your own use cases."

---

## Common Questions & Answers

**Q: Can I use my own fine-tuned model?**
A: Yes! Any model deployed to a Databricks serving endpoint can be used. Just configure it as a resource when creating the app.

**Q: What about large PDFs?**
A: The app automatically scales workers based on document size. For very large documents, you might increase the app's compute size.

**Q: How is authentication handled for end users?**
A: End users authenticate via Databricks workspace SSO. The app runs with its Service Principal's permissions, but user identity is available via `X-Forwarded-Email` headers.

**Q: Can this app access Unity Catalog tables?**
A: Yes, through the SQL Warehouse resource. The app can read from and write to any tables the Service Principal has access to.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "DATABRICKS_SERVING_ENDPOINT not set" | Ensure the serving endpoint resource is added in app configuration |
| "Could not retrieve authentication token" | Check that the app has proper permissions on the serving endpoint |
| Slow extraction | Consider increasing app compute size or using a faster serving endpoint |
| "SQL_WAREHOUSE_ID not set" | Add the SQL Warehouse as a resource if using the Delta Table export feature |

---

## Workshop Participant Hands-On

After the demo, have participants:

1. Create their own app following the same steps
2. Upload a different PDF document
3. Modify the extraction prompt for a specific use case (e.g., "Extract only dates and dollar amounts")
4. Save results to their own Delta table

---

## Wrap-Up Talking Points

1. **Ease of Deployment**: "From code to production app in minutes, with automatic SSL, authentication, and scaling."

2. **Integration**: "Seamless integration with Databricks AI infrastructure - serving endpoints, SQL Warehouses, Unity Catalog."

3. **Security**: "No credentials in code, automatic token management, workspace-level access control."

4. **Extensibility**: "This pattern works for any AI use case - chat apps, image analysis, recommendation systems, and more."
