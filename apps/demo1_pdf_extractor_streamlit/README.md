# PDF Text Extractor with Databricks Vision AI

A Streamlit application that extracts text from PDF documents using Databricks Vision AI models. Ideal for digitizing forms, documents, scanned materials, and structured data extraction.

## Features

- **PDF Upload**: Simple drag-and-drop interface for PDF files
- **AI-Powered Extraction**: Uses Databricks Vision AI to extract and transcribe text
- **Customizable Prompts**: Tailor the extraction prompt for different document types
- **Side-by-Side View**: Compare original PDF pages with extracted text
- **Smart Processing**: Automatically scales workers based on document size
- **Multiple Export Options**:
  - Download as CSV
  - Download as plain text
  - Save directly to Delta table via SQL Warehouse
- **Production Ready**: Built with error handling, progress tracking, and clean UI

## How It Works

1. **Upload**: Select a PDF document
2. **Configure**: Optionally customize the extraction prompt
3. **Extract**: Click "Extract Text" to process with Vision AI
4. **Review**: Browse results page-by-page in side-by-side view
5. **Export**: Download or save to Delta table

## Architecture

```
demo1_pdf_extractor_streamlit/
├── app.py              # Streamlit UI and main application logic
├── pdf_processor.py    # PDF conversion and Vision AI integration
├── app.yml             # Databricks Apps configuration
├── requirements.txt    # Python dependencies
└── sample_pdf.pdf      # Sample document for testing
```

## Configuration

### Environment Variables

Set these via Databricks Apps resource configuration:

| Variable | Source | Description |
|----------|--------|-------------|
| `DATABRICKS_SERVING_ENDPOINT` | Serving Endpoint resource | Vision AI model endpoint name |
| `SQL_WAREHOUSE_ID` | SQL Warehouse resource | Required for "Save to Delta Table" feature |

### App Resources

When creating the Databricks App, add these resources:

1. **Serving Endpoint**: Select your vision-capable model endpoint
2. **SQL Warehouse**: Select a warehouse for Delta table operations (optional)

## Prerequisites

- A Databricks Model Serving Endpoint with a vision-capable model (e.g., Claude, GPT-4V)
- (Optional) A SQL Warehouse for Delta table export functionality
- Databricks workspace with Apps enabled

## Deploying to Databricks Apps

1. Create a new Databricks App (custom app)
2. Add a **Serving Endpoint** resource pointing to your vision model
3. (Optional) Add a **SQL Warehouse** resource for Delta table export
4. Sync code from Git or upload files
5. Deploy the app

Authentication is handled automatically via the Databricks SDK - no tokens or credentials needed in code.

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set Databricks credentials (for local development)
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=your-token
export DATABRICKS_SERVING_ENDPOINT=your-endpoint-name

# Run the app
streamlit run app.py
```

## Usage Tips

### Customizing Extraction Prompts

The default prompt extracts text as markdown with bolded keys. Customize for your use case:

- **Forms**: "Extract all key-value pairs in a structured format"
- **Tables**: "Convert the table data into CSV format"  
- **Invoices**: "Extract invoice number, date, line items, and total amount"
- **Contracts**: "Extract party names, dates, and key terms"

### Performance Notes

- Processing is parallelized automatically based on document size
- Larger documents (20+ pages) use more concurrent workers
- The Vision AI model processes one page at a time per worker

## Example Use Cases

1. **Form Digitization**: Convert paper forms to structured data
2. **Invoice Processing**: Extract invoice details for accounting systems
3. **Document Archival**: Digitize and index historical documents
4. **Table Extraction**: Pull tables from PDF reports into DataFrames
5. **Contract Analysis**: Extract key terms from legal documents

## Technical Details

### Processing Pipeline

1. **PDF → Images**: Convert PDF pages to high-resolution PNG images (300 DPI)
2. **Base64 Encoding**: Encode images for API transmission
3. **Vision AI**: Send each image to the model with the extraction prompt
4. **Parallel Processing**: Use ThreadPoolExecutor with adaptive worker scaling
5. **Result Compilation**: Combine page results into a DataFrame with metadata

### Adaptive Worker Scaling

The app automatically adjusts concurrency based on document size:
- Small documents (1-5 pages): 3 workers
- Medium documents (6-20 pages): 5 workers  
- Large documents (20+ pages): 8 workers

Rate limiting is handled with automatic retries and backoff.

## Workshop Notes

This app demonstrates:
- Integration with Databricks Model Serving Endpoints
- OAuth authentication via Databricks SDK
- Real-time progress tracking in Streamlit
- Side-by-side document comparison UI
- Multiple data export options (CSV, text, Delta)
- SQL Warehouse integration for data persistence
- Production-ready error handling patterns
