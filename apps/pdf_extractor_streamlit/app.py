import os
import streamlit as st
import pandas as pd
import tempfile
from databricks.sdk.core import Config
from pdf_processor import convert_pdf_to_base64, process_images_adaptive

# Page config
st.set_page_config(
    page_title="PDF Text Extractor",
    page_icon=":page_facing_up:",
    layout="wide"
)

# Initialize Databricks configuration
@st.cache_resource
def get_databricks_config():
    return Config()

cfg = get_databricks_config()

# Get Databricks configuration
DATABRICKS_HOST = cfg.host
if not DATABRICKS_HOST.endswith('/'):
    DATABRICKS_HOST += '/'
DATABRICKS_BASE_URL = DATABRICKS_HOST + 'serving-endpoints/'

# Get authentication - try different methods
DATABRICKS_TOKEN = None
try:
    # Try to get token from Config
    auth_result = cfg.authenticate()
    if isinstance(auth_result, dict) and 'Authorization' in auth_result:
        # Extract token from Authorization header (format: "Bearer <token>")
        DATABRICKS_TOKEN = auth_result['Authorization'].replace('Bearer ', '')
    elif hasattr(cfg, 'token') and cfg.token:
        DATABRICKS_TOKEN = cfg.token
except Exception as e:
    st.error(f"Error getting authentication token: {e}")

if not DATABRICKS_TOKEN:
    st.error("Could not retrieve Databricks authentication token. Please check app permissions.")
    st.stop()

# Get model endpoint from environment
SERVING_ENDPOINT = os.getenv("DATABRICKS_SERVING_ENDPOINT")

if not SERVING_ENDPOINT:
    st.error("DATABRICKS_SERVING_ENDPOINT environment variable is not set. Please configure it in your Databricks App settings.")
    st.stop()

# Initialize session state
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "stats" not in st.session_state:
    st.session_state.stats = None

# Custom CSS for cleaner UI
st.markdown("""
    <style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
    }
    </style>
    """, unsafe_allow_html=True)

# Header
st.title("PDF Text Extractor")
st.caption("Extract text from PDFs using Databricks Vision AI")

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    st.text_input(
        "Model Endpoint",
        value=SERVING_ENDPOINT,
        disabled=True,
        help="Configured via DATABRICKS_SERVING_ENDPOINT environment variable"
    )
    
    st.divider()
    
    st.subheader("Processing Settings")
    
    dpi = st.slider(
        "Image Resolution (DPI)",
        min_value=150,
        max_value=600,
        value=300,
        step=50,
        help="Higher DPI = better quality but slower processing"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        initial_workers = st.number_input("Initial", min_value=1, max_value=20, value=5, help="Starting workers")
    with col2:
        min_workers = st.number_input("Min", min_value=1, max_value=10, value=1, help="Minimum workers")
    with col3:
        max_workers = st.number_input("Max", min_value=5, max_value=50, value=10, help="Maximum workers")
    
    st.divider()
    
    st.subheader("Extraction Prompt")
    extraction_prompt = st.text_area(
        "Custom Prompt",
        value="Transcribe the following form into markdown. Please bold all keys in key value pairs, and output sections with section headers.",
        height=150,
        help="Customize how the model extracts text from your PDF"
    )
    
    st.divider()
    
    st.subheader("Output Options")
    
    output_table = st.text_input(
        "Delta Table Path (optional)",
        placeholder="catalog.schema.table_name",
        help="Leave empty to skip saving to Delta table"
    )

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=['pdf'],
        help="Select a PDF file to extract text from"
    )

with col2:
    st.markdown("### Configuration Summary")
    st.markdown(f"**Model:** `{SERVING_ENDPOINT}`")
    st.markdown(f"**Resolution:** {dpi} DPI")
    st.markdown(f"**Workers:** {initial_workers} - {max_workers}")

if uploaded_file is not None:
    st.success(f"Loaded: {uploaded_file.name}")
    
    # Process button
    if st.button("Extract Text", type="primary", use_container_width=True):
        # Reset state
        st.session_state.processing_complete = False
        st.session_state.results_df = None
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Step 1: Convert PDF to images
            st.markdown("---")
            st.subheader("Processing Status")
            
            progress_container = st.container()
            with progress_container:
                status_text = st.empty()
                progress_bar = st.progress(0)
                stats_cols = st.columns(4)
                
                def update_progress(current, total, message, stats=None):
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(progress)
                    status_text.text(f"{message} ({current}/{total})")
                    
                    if stats:
                        with stats_cols[0]:
                            st.metric("Workers", stats.get('workers', '-'))
                        with stats_cols[1]:
                            st.metric("Rate Limits", stats.get('rate_limits', '-'))
                        with stats_cols[2]:
                            status = "Success" if stats.get('success') else "Failed"
                            st.metric("Last Page", status)
                        with stats_cols[3]:
                            st.metric("Progress", f"{int(progress * 100)}%")
                
                status_text.text("Converting PDF to images...")
                df = convert_pdf_to_base64(tmp_path, dpi=dpi, progress_callback=update_progress)
                
                st.success(f"Converted {len(df)} pages to images")
                
                # Step 2: Extract text from images
                status_text.text("Extracting text with AI model...")
                
                results_series, stats = process_images_adaptive(
                    prompt=extraction_prompt,
                    images=df['base64_img'],
                    databricks_token=DATABRICKS_TOKEN,
                    databricks_url=DATABRICKS_BASE_URL,
                    model=SERVING_ENDPOINT,
                    initial_workers=initial_workers,
                    min_workers=min_workers,
                    max_workers=max_workers,
                    progress_callback=update_progress
                )
                
                df['transcription'] = results_series
                
                # Store results
                st.session_state.results_df = df
                st.session_state.stats = stats
                st.session_state.processing_complete = True
                
                progress_bar.progress(1.0)
                st.success("Text extraction complete!")
        
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
        
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

# Display results
if st.session_state.processing_complete and st.session_state.results_df is not None:
    st.markdown("---")
    st.subheader("Results Summary")
    
    stats = st.session_state.stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Pages", stats['total'])
    with col2:
        st.metric("Successful", stats['success'], delta=f"{stats['success_rate']:.1f}%")
    with col3:
        st.metric("Failed", stats['failed'])
    with col4:
        st.metric("Success Rate", f"{stats['success_rate']:.1f}%")
    
    st.markdown("---")
    st.subheader("Export Options")
    
    df = st.session_state.results_df
    
    # Export buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Download CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="extracted_text.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Copy to clipboard (just the transcriptions)
        transcriptions = "\n\n---PAGE BREAK---\n\n".join(
            df['transcription'].astype(str).tolist()
        )
        st.download_button(
            label="Download Text",
            data=transcriptions,
            file_name="extracted_text.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        # Save to Delta table
        if output_table and output_table.strip():
            if st.button("Save to Delta Table", use_container_width=True):
                try:
                    from pyspark.sql import SparkSession
                    spark = SparkSession.builder.getOrCreate()
                    
                    # Drop base64 column for storage efficiency
                    df_to_save = df.drop(columns=['base64_img'])
                    spark_df = spark.createDataFrame(df_to_save)
                    
                    spark_df.write \
                        .format("delta") \
                        .mode("overwrite") \
                        .option("overwriteSchema", "true") \
                        .saveAsTable(output_table)
                    
                    st.success(f"Saved to {output_table}")
                except Exception as e:
                    st.error(f"Error saving to Delta: {str(e)}")
        else:
            st.button("Save to Delta Table", disabled=True, use_container_width=True, help="Enter a table path in sidebar")
    
    st.markdown("---")
    st.subheader("Extracted Text by Page")
    
    # Create tabs for each page
    if len(df) > 0:
        # Show page selector for easier navigation
        page_num = st.selectbox(
            "Jump to page:",
            options=range(1, len(df) + 1),
            format_func=lambda x: f"Page {x}"
        )
        
        selected_page = df[df['page_num'] == page_num].iloc[0]
        
        with st.expander(f"Page {selected_page['page_num']}", expanded=True):
            transcription = selected_page['transcription']
            
            if str(transcription).startswith("ERROR:"):
                st.error(transcription)
            else:
                st.markdown(transcription)
            
            st.caption(f"Document ID: {selected_page['doc_id']}")
    
    # Show full dataframe (without base64 images)
    with st.expander("View Full Data Table"):
        display_df = df.drop(columns=['base64_img'])
        st.dataframe(display_df, use_container_width=True, height=400)

else:
    # Show instructions when no file is uploaded
    if uploaded_file is None:
        st.info("Upload a PDF file to get started")
        
        with st.expander("How it works"):
            st.markdown("""
            ### PDF Text Extraction Process
            
            1. **Upload**: Select a PDF file
            2. **Convert**: PDF pages are converted to high-resolution images
            3. **Extract**: Databricks Vision AI model analyzes each page and extracts text
            4. **Export**: Download results as CSV/text or save to a Delta table
            
            ### Tips for Best Results
            
            - Use **higher DPI** (400-600) for documents with small text
            - Adjust **workers** based on your endpoint's throughput:
              - Pay-Per-Token: 5-10 workers
              - Provisioned (200 units): 30-40 workers
            - Customize the **extraction prompt** for specific document types
            - The system automatically handles rate limiting and retries
            
            ### Model Information
            
            This app uses a **Databricks Vision AI** model which can:
            - Read and understand text in images
            - Preserve document structure and formatting
            - Handle forms, tables, and complex layouts
            - Output structured markdown
            """)
