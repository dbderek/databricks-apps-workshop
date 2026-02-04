# PDF Text Extractor with Databricks Vision AI

A sleek Streamlit app that extracts text from PDF documents using Databricks Vision AI models. Perfect for digitizing forms, documents, and scanned materials.

## Features

- **PDF Upload**: Simple drag-and-drop PDF upload interface
- **AI-Powered Extraction**: Uses Databricks Vision AI to extract text from PDF pages
- **Adaptive Processing**: Automatically adjusts concurrency based on API rate limits
- **Real-time Progress**: Live progress tracking with detailed statistics
- **Multiple Export Options**:
  - Download as CSV
  - Download as plain text
  - Save directly to Delta table
- **Configurable**: Adjust DPI, worker count, and extraction prompts
- **Clean UI**: Modern, responsive interface with clear status indicators

## How It Works

1. **Upload PDF**: Select a PDF file from your computer
2. **Configure Settings**: Adjust DPI, workers, and extraction prompt (optional)
3. **Extract**: Click "Extract Text" to start processing
4. **Export**: Download results or save to Delta table

## Architecture

The app is split into two files:
- `app.py`: Contains all Streamlit UI logic
- `pdf_processor.py`: Contains PDF processing and AI model logic

This separation keeps the code clean and maintainable.

## Configuration

The model endpoint is configured via the `DATABRICKS_SERVING_ENDPOINT` environment variable set at the Databricks App level.

### Environment Variables

Set these in your Databricks App configuration:
- `DATABRICKS_SERVING_ENDPOINT`: Your Databricks Vision AI serving endpoint name (required)

### Sidebar Settings

- **Image Resolution**: DPI for PDF conversion (150-600, default: 300)
- **Workers**: Initial/Min/Max concurrent workers for processing
- **Extraction Prompt**: Customize how the model extracts text
- **Delta Table Path**: Optional path to save results

### Worker Configuration Guidelines

- **Pay-Per-Token endpoints**: 5-10 workers
- **Provisioned Throughput (200 units)**: 30-40 workers
- The system automatically adjusts based on rate limits

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set Databricks credentials
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=your-token

# Run the app
streamlit run app.py
```

## Deploying to Databricks Apps

1. Ensure you have access to a Vision AI serving endpoint
2. Set the `DATABRICKS_SERVING_ENDPOINT` environment variable in your Databricks App settings
3. Deploy using Databricks Apps
4. The app will automatically authenticate using the app service principal

## Usage Tips

### For Best Results

- **High-quality scans**: Use 400-600 DPI for documents with small text
- **Custom prompts**: Tailor the extraction prompt to your document type
  - Forms: "Extract all key-value pairs in a structured format"
  - Tables: "Convert the table data into CSV format"
  - Invoices: "Extract invoice number, date, items, and total"

### Performance

- Higher DPI = Better quality but slower processing
- More workers = Faster but may hit rate limits
- The system automatically backs off when hitting rate limits

## Example Use Cases

1. **Form Digitization**: Convert paper forms to structured data
2. **Invoice Processing**: Extract invoice details for accounting
3. **Document Archival**: Digitize historical documents
4. **Table Extraction**: Pull tables from PDF reports into DataFrames
5. **Contract Analysis**: Extract key terms from legal documents

## Technical Details

### PDF Processing Pipeline

1. **Image Conversion**: PDF pages → High-res PNG images (base64 encoded)
2. **AI Processing**: Each image sent to Databricks Vision AI model
3. **Adaptive Rate Limiting**: Automatically adjusts workers based on API responses
4. **Error Handling**: Retries failed pages with exponential backoff
5. **Result Compilation**: Combines all page results into a DataFrame

### Adaptive Rate Limiting

The processor automatically:
- Reduces workers when hitting rate limits
- Increases workers when processing is smooth
- Retries failed requests with backoff
- Tracks performance metrics in real-time

## Workshop Notes

This app demonstrates:
- Integration with Databricks Vision AI models
- Production-ready error handling and rate limiting
- Clean separation of concerns (UI vs logic)
- Real-time progress tracking in Streamlit
- Multiple data export options
- Delta table integration
- Concurrent processing with ThreadPoolExecutor
- Environment-based configuration
