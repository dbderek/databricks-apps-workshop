# Demo 1: PDF Text Extraction with Vision AI

## Workshop User Guide

This guide walks you through building and deploying a PDF text extraction application using Databricks Apps and Vision AI.

---

## What You Will Build

A Streamlit application that:
- Uploads PDF documents
- Extracts text using Databricks Vision AI
- Displays results in a side-by-side view
- Exports to CSV, text, or Delta tables

**Estimated Time**: 15-20 minutes

**Key Concepts**:
- Databricks Apps deployment
- Model Serving Endpoints integration
- SQL Warehouse connectivity
- Automatic OAuth authentication

---

## Prerequisites

Before starting, ensure you have:
- Access to a Databricks workspace with Apps enabled
- A Model Serving Endpoint with a vision-capable model
- (Optional) A SQL Warehouse for Delta table export

---

## Step 1: Create the App

1. In your Databricks workspace, navigate to **Compute** > **Apps**
2. Click **New** > **Create app**
3. Select **Create a custom app**
4. Fill in the details:
   - **Name**: `demo-1-pdf-text-extraction`
   - **Description**: "PDF text extraction with Vision AI"
5. Click **Next: Configure**

---

## Step 2: Configure App Resources

### Add Serving Endpoint

1. Under **App resources**, click **Add resource**
2. Select **Serving endpoint**
3. Choose your vision-capable model endpoint

This grants the app permission to call the model and provides the `DATABRICKS_SERVING_ENDPOINT` environment variable automatically.

### Add SQL Warehouse (Optional)

1. Click **Add resource** again
2. Select **SQL Warehouse**
3. Choose your warehouse

This enables the "Save to Delta Table" feature.

### Compute Size

Leave at **Medium** for this demo. Larger sizes are available for memory-intensive workloads.

---

## Step 3: Deploy the App

1. Click **Create app**
2. Wait for provisioning (2-3 minutes)

While waiting, note that Databricks Apps:
- Runs your app in a managed container
- Handles authentication automatically via the Databricks SDK
- Injects environment variables for configured resources
- Provides a unique URL for your app

---

## Step 4: Upload Source Code

Once the app is provisioned:

1. Click **Sync from Git** or **Upload files**
2. If using Git, configure:
   - Repository URL
   - Path: `apps/demo1_pdf_extractor_streamlit`
   - Branch: `main`
3. Click **Deploy**

The app will restart with your code.

---

## Step 5: Use the Application

### Upload a PDF

1. Open the app URL
2. Click the file uploader and select a PDF document
3. Optionally customize the extraction prompt

### Extract Text

1. Click **Extract Text**
2. Watch the progress bar as pages are processed
3. The app automatically scales workers based on document size

### Review Results

- Use the page selector to navigate between pages
- View the original PDF on the left, extracted text on the right
- Verify extraction quality page by page

### Export Options

- **Download as CSV**: Get a spreadsheet with page numbers and text
- **Download as Text**: Get plain text output
- **Save to Delta Table**: Persist to Unity Catalog for downstream analytics

---

## Key Features Explained

### Automatic Authentication

The app uses the Databricks SDK for authentication. No API keys or tokens are stored in code - credentials are managed automatically.

```python
cfg = Config()
auth_result = cfg.authenticate()
```

### Environment Variable Injection

Resources configured in the app settings are available as environment variables:

```python
model_endpoint = os.getenv("DATABRICKS_SERVING_ENDPOINT")
```

### Customizable Prompts

Tailor extraction for your use case:
- **Forms**: "Extract all key-value pairs in a structured format"
- **Tables**: "Convert the table data into CSV format"
- **Invoices**: "Extract invoice number, date, line items, and total"

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "DATABRICKS_SERVING_ENDPOINT not set" | Add the serving endpoint as a resource in app configuration |
| "Could not retrieve authentication token" | Verify the app has permissions on the serving endpoint |
| Slow extraction | Increase app compute size or use a faster endpoint |
| "SQL_WAREHOUSE_ID not set" | Add a SQL Warehouse resource for Delta table export |

---

## FAQ

**Can I use my own model?**
Yes. Any model deployed to a Databricks serving endpoint can be used.

**How are large documents handled?**
The app automatically scales workers based on page count.

**How is authentication handled?**
End users authenticate via workspace SSO. The app uses its Service Principal for API calls.

**Can the app write to Unity Catalog?**
Yes, through the SQL Warehouse resource.

---

## Next Steps

Try these exercises:
1. Upload a different PDF document
2. Modify the extraction prompt for a specific use case
3. Save results to your own Delta table
4. Explore the code in `app.py` and `pdf_processor.py`

---

## Summary

You have deployed a production-ready PDF extraction app that:
- Integrates with Databricks AI infrastructure
- Handles authentication automatically
- Provides multiple export options
- Can be extended for your own use cases
