"""
PDF Text Extractor - Streamlit Application
Extracts text from PDF documents using Databricks Vision AI
"""

import os
import base64
import tempfile
import streamlit as st
import pandas as pd
from databricks.sdk.core import Config
from pdf_processor import convert_pdf_to_base64, extract_text_from_images


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="PDF Text Extractor",
    page_icon=":page_facing_up:",
    layout="wide"
)


# =============================================================================
# DATABRICKS AUTHENTICATION & CONFIGURATION
# =============================================================================

@st.cache_resource
def initialize_databricks():
    """
    Initialize Databricks configuration and authentication.
    
    Returns:
        tuple: (databricks_token, base_url, model_endpoint)
    """
    # Get Databricks config
    cfg = Config()
    
    # Build serving endpoint URL
    host = cfg.host
    if not host.endswith('/'):
        host += '/'
    base_url = host + 'serving-endpoints/'
    
    # Get authentication token
    token = None
    try:
        auth_result = cfg.authenticate()
        if isinstance(auth_result, dict) and 'Authorization' in auth_result:
            token = auth_result['Authorization'].replace('Bearer ', '')
        elif hasattr(cfg, 'token') and cfg.token:
            token = cfg.token
    except Exception as e:
        st.error(f"Authentication error: {e}")
        st.stop()
    
    if not token:
        st.error("Could not retrieve authentication token. Check app permissions.")
        st.stop()
    
    # Get model endpoint from environment
    model_endpoint = os.getenv("DATABRICKS_SERVING_ENDPOINT")
    if not model_endpoint:
        st.error("DATABRICKS_SERVING_ENDPOINT environment variable not set.")
        st.stop()
    
    return token, base_url, model_endpoint

# Initialize once and cache
DATABRICKS_TOKEN, DATABRICKS_BASE_URL, SERVING_ENDPOINT = initialize_databricks()


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None


# =============================================================================
# CUSTOM STYLING
# =============================================================================

st.markdown("""
    <style>
    .main { padding: 2rem; }
    h1 { margin-bottom: 0.5rem !important; }
    .stFileUploader {
        border: 2px dashed #666;
        border-radius: 10px;
        padding: 2rem;
        background-color: rgba(128, 128, 128, 0.1);
    }
    .stTextArea textarea { font-family: 'Monaco', 'Courier New', monospace; }
    .streamlit-expanderHeader { font-size: 1.1rem; font-weight: 600; }
    
    /* Make all buttons (regular and download) the same height and style */
    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        padding: 0.75rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        height: 3rem !important;
        line-height: 1.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_worker_config(num_pages):
    """
    Calculate optimal worker configuration based on document size.
    
    Args:
        num_pages: Number of pages in the document
    
    Returns:
        tuple: (initial_workers, min_workers, max_workers)
    """
    if num_pages <= 5:
        return 3, 1, 5
    elif num_pages <= 20:
        return 5, 2, 10
    else:
        return 8, 3, 15


def save_to_delta_table(df, table_path):
    """
    Save extracted data to Delta table using Databricks SQL.
    
    Args:
        df: DataFrame with extracted text
        table_path: Full path to Delta table (catalog.schema.table)
    """
    from databricks import sql
    
    cfg = Config()
    warehouse_id = os.getenv("SQL_WAREHOUSE_ID")
    
    if not warehouse_id:
        raise ValueError("SQL_WAREHOUSE_ID environment variable not set")
    
    # Connect to warehouse
    conn = sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        credentials_provider=lambda: cfg.authenticate
    )
    
    # Prepare data (remove base64 images)
    df_to_save = df[['page_num', 'transcription', 'doc_id']]
    
    # Create table
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_path} (
        page_num BIGINT,
        transcription STRING,
        doc_id STRING
    ) USING DELTA
    """
    
    with conn.cursor() as cursor:
        cursor.execute(create_sql)
    
    # Insert data row by row
    for _, row in df_to_save.iterrows():
        # Escape single quotes in transcription
        safe_text = row['transcription'].replace("'", "''")
        insert_sql = f"""
        INSERT INTO {table_path} (page_num, transcription, doc_id)
        VALUES ({row['page_num']}, '{safe_text}', '{row['doc_id']}')
        """
        with conn.cursor() as cursor:
            cursor.execute(insert_sql)
    
    conn.close()
    return len(df_to_save)


# =============================================================================
# MAIN APPLICATION UI
# =============================================================================

# Header
st.title("PDF Text Extractor")
st.caption(f"Extract text from PDFs using Databricks Vision AI • Model: {SERVING_ENDPOINT}")
st.markdown("---")

# Instructions (collapsed by default)
with st.expander("How it works", expanded=False):
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

# File upload
uploaded_file = st.file_uploader(
    "Upload PDF Document",
    type=['pdf'],
    help="Select a PDF file to extract text from"
)

# Main processing logic
if uploaded_file is not None:
    # Extraction prompt configuration
    extraction_prompt = st.text_area(
        "Extraction Prompt",
        value="Transcribe the following document into markdown. Please bold all keys in key value pairs, and output sections with section headers.",
        height=120,
        help="Customize how the AI extracts and formats text"
    )
    
    # Process button
    if st.button("Extract Text", type="primary", use_container_width=True):
        # Reset state
        st.session_state.processing_complete = False
        st.session_state.results_df = None
        st.session_state.uploaded_file_name = uploaded_file.name
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            st.markdown("---")
            
            with st.spinner("Processing your document..."):
                # Step 1: Convert PDF to images
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                status_text.info("Converting PDF pages to images...")
                df = convert_pdf_to_base64(tmp_path, dpi=300)
                progress_bar.progress(0.3)
                
                # Step 2: Extract text using Vision AI
                status_text.info(f"Extracting text from {len(df)} pages using AI...")
                
                # Auto-configure workers based on document size
                initial_workers, min_workers, max_workers = calculate_worker_config(len(df))
                
                # Process all pages
                results_series, stats = extract_text_from_images(
                    prompt=extraction_prompt,
                    images=df['base64_img'],
                    databricks_token=DATABRICKS_TOKEN,
                    databricks_url=DATABRICKS_BASE_URL,
                    model=SERVING_ENDPOINT,
                    initial_workers=initial_workers,
                    min_workers=min_workers,
                    max_workers=max_workers
                )
                
                # Add results to dataframe
                df['transcription'] = results_series
                progress_bar.progress(1.0)
                
                # Store in session state
                st.session_state.results_df = df
                st.session_state.processing_complete = True
                
                status_text.success(f"Successfully extracted text from {stats['success']}/{stats['total']} pages!")
        
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
        
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


# =============================================================================
# RESULTS DISPLAY
# =============================================================================

if st.session_state.processing_complete and st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    st.markdown("---")
    st.subheader("Extracted Content")
    
    # Side-by-side view: PDF preview and extracted text
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
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Display extracted text
        transcription = selected_page['transcription']
        
        if str(transcription).startswith("ERROR:"):
            st.error(transcription)
        else:
            # Scrollable text container
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
    
    # Export options
    st.markdown("---")
    st.subheader("Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    # CSV download
    with col1:
        csv = df[['page_num', 'transcription', 'doc_id']].to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"{st.session_state.uploaded_file_name}_extracted.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv"
        )
    
    # Text download
    with col2:
        transcriptions = "\n\n---PAGE BREAK---\n\n".join(
            df['transcription'].astype(str).tolist()
        )
        st.download_button(
            label="Download as Text",
            data=transcriptions,
            file_name=f"{st.session_state.uploaded_file_name}_extracted.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_text"
        )
    
    # Delta table save button
    with col3:
        if st.button("Save to Delta Table", use_container_width=True, key="open_delta_modal"):
            st.session_state.show_delta_modal = True
    
    # Delta table modal
    if st.session_state.get("show_delta_modal", False):
        with st.form("delta_table_form"):
            st.subheader("Save to Delta Table")
            
            delta_table_path = st.text_input(
                "Enter Delta Table Path",
                placeholder="catalog.schema.table_name",
                help="Full path to the Delta table"
            )
            
            col_submit, col_cancel = st.columns(2)
            
            with col_submit:
                submitted = st.form_submit_button("Save", use_container_width=True, type="primary")
            
            with col_cancel:
                cancelled = st.form_submit_button("Cancel", use_container_width=True)
            
            if submitted and delta_table_path:
                try:
                    rows_saved = save_to_delta_table(df, delta_table_path)
                    st.success(f"Successfully saved {rows_saved} rows to {delta_table_path}")
                    st.session_state.show_delta_modal = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving to Delta: {str(e)}")
            
            if cancelled:
                st.session_state.show_delta_modal = False
                st.rerun()

elif uploaded_file is None:
    st.info("Upload a PDF document to get started")