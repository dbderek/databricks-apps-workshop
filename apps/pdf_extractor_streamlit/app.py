import os
import streamlit as st
import pandas as pd
import tempfile
import base64
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
    auth_result = cfg.authenticate()
    if isinstance(auth_result, dict) and 'Authorization' in auth_result:
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
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

# Custom CSS for better styling and dark mode support
st.markdown("""
    <style>
    /* Main container */
    .main {
        padding: 2rem;
    }
    
    /* Headers */
    h1 {
        margin-bottom: 0.5rem !important;
    }
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #666;
        border-radius: 10px;
        padding: 2rem;
        background-color: rgba(128, 128, 128, 0.1);
    }
    
    /* Text areas */
    .stTextArea textarea {
        font-family: 'Monaco', 'Courier New', monospace;
    }
    
    /* Buttons */
    .stButton button {
        width: 100%;
        padding: 0.75rem;
        font-size: 1rem;
        font-weight: 600;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* Download buttons section */
    .download-section {
        background-color: rgba(128, 128, 128, 0.1);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Header
st.title("PDF Text Extractor")
st.caption(f"Extract text from PDFs using Databricks Vision AI • Model: {SERVING_ENDPOINT}")
st.markdown("---")

# Step 1: Upload and Configuration
uploaded_file = st.file_uploader(
    "Upload PDF Document",
    type=['pdf'],
    help="Select a PDF file to extract text from"
)

if uploaded_file is not None:
    # Configuration options
    col1, col2 = st.columns(2)
    
    with col1:
        extraction_prompt = st.text_area(
            "Extraction Prompt",
            value="Transcribe the following document into markdown. Please bold all keys in key value pairs, and output sections with section headers.",
            height=120,
            help="Customize how the AI extracts and formats text"
        )
    
    with col2:
        output_table = st.text_input(
            "Delta Table Path (optional)",
            placeholder="catalog.schema.table_name",
            help="Leave empty to skip saving to Delta table"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        process_button = st.button("Extract Text", type="primary", use_container_width=True)
    
    # Process the PDF
    if process_button:
        st.session_state.processing_complete = False
        st.session_state.results_df = None
        st.session_state.uploaded_file_name = uploaded_file.name
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            st.markdown("---")
            
            # Processing status
            status_container = st.container()
            with status_container:
                with st.spinner("Processing your document..."):
                    # Step 1: Convert PDF to images
                    status_text = st.empty()
                    progress_bar = st.progress(0)
                    
                    status_text.info("Converting PDF pages to images...")
                    df = convert_pdf_to_base64(tmp_path, dpi=300)
                    progress_bar.progress(0.3)
                    
                    status_text.info(f"Extracting text from {len(df)} pages using AI...")
                    
                    # Step 2: Extract text from images (with smart worker configuration)
                    # Auto-configure workers based on document size
                    num_pages = len(df)
                    if num_pages <= 5:
                        initial_workers, min_workers, max_workers = 3, 1, 5
                    elif num_pages <= 20:
                        initial_workers, min_workers, max_workers = 5, 2, 10
                    else:
                        initial_workers, min_workers, max_workers = 8, 3, 15
                    
                    results_series, stats = process_images_adaptive(
                        prompt=extraction_prompt,
                        images=df['base64_img'],
                        databricks_token=DATABRICKS_TOKEN,
                        databricks_url=DATABRICKS_BASE_URL,
                        model=SERVING_ENDPOINT,
                        initial_workers=initial_workers,
                        min_workers=min_workers,
                        max_workers=max_workers
                    )
                    
                    df['transcription'] = results_series
                    progress_bar.progress(1.0)
                    
                    # Store results
                    st.session_state.results_df = df
                    st.session_state.processing_complete = True
                    
                    status_text.success(f"Successfully extracted text from {stats['success']}/{stats['total']} pages!")
        
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
        
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

# Display results
if st.session_state.processing_complete and st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    st.markdown("---")
    st.subheader("Extracted Content")
    
    # Create two columns for side-by-side view
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.markdown("#### PDF Preview")
        
        # Page selector
        page_num = st.selectbox(
            "Select page to view:",
            options=range(1, len(df) + 1),
            format_func=lambda x: f"Page {x} of {len(df)}"
        )
        
        # Display PDF page as image
        selected_page = df[df['page_num'] == page_num].iloc[0]
        img_data = base64.b64decode(selected_page['base64_img'])
        st.image(img_data, use_column_width=True)
    
    with col_right:
        st.markdown("#### Extracted Text")
        
        # Add some spacing to align with the selector
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Display extracted text
        transcription = selected_page['transcription']
        
        if str(transcription).startswith("ERROR:"):
            st.error(transcription)
        else:
            # Display in a scrollable container
            st.markdown(
                f"""
                <div style="
                    background-color: rgba(128, 128, 128, 0.1);
                    padding: 1.5rem;
                    border-radius: 10px;
                    height: 600px;
                    overflow-y: auto;
                    font-family: 'Monaco', 'Courier New', monospace;
                    font-size: 0.9rem;
                ">
                    {transcription}
                </div>
                """,
                unsafe_allow_html=True
            )
    
    # Export Options at the bottom
    st.markdown("---")
    st.subheader("Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = df[['page_num', 'transcription', 'doc_id']].to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"{st.session_state.uploaded_file_name}_extracted.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        transcriptions = "\n\n---PAGE BREAK---\n\n".join(
            df['transcription'].astype(str).tolist()
        )
        st.download_button(
            label="Download as Text",
            data=transcriptions,
            file_name=f"{st.session_state.uploaded_file_name}_extracted.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        if output_table and output_table.strip():
            if st.button("Save to Delta Table", use_container_width=True):
                try:
                    from pyspark.sql import SparkSession
                    spark = SparkSession.builder.getOrCreate()
                    
                    df_to_save = df.drop(columns=['base64_img'])
                    spark_df = spark.createDataFrame(df_to_save)
                    
                    spark_df.write \
                        .format("delta") \
                        .mode("overwrite") \
                        .option("overwriteSchema", "true") \
                        .saveAsTable(output_table)
                    
                    st.success(f"Saved to {output_table}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.button("Save to Delta Table", disabled=True, use_container_width=True, help="Enter table path above")

elif uploaded_file is None:
    # Show instructions when no file is uploaded
    st.info("Upload a PDF document to get started")
    
    with st.expander("How it works", expanded=True):
        st.markdown("""
        ### Simple 3-Step Process
        
        1. **Upload** - Select your PDF document
        2. **Configure** - Optionally customize the extraction prompt
        3. **Extract** - Click the button and watch the AI extract text
        
        ### Features
        
        - **Side-by-side view** - Compare original PDF with extracted text
        - **Multiple export options** - Download as CSV, text file, or save to Delta
        - **Smart processing** - Automatically adjusts to document size
        - **Production ready** - Built on Databricks Vision AI with error handling
        
        ### Best For
        
        - Forms and structured documents
        - Scanned documents and images
        - Tables and financial reports
        - Contracts and legal documents
        """)
