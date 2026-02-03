"""
PDF Processing Module
Handles PDF to image conversion and AI-powered text extraction with adaptive rate limiting
"""

import base64
import time
import random
import threading
import pandas as pd
import fitz  # PyMuPDF
from openai import OpenAI
from collections import deque
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


# =============================================================================
# CONSTANTS
# =============================================================================

# Error substrings that indicate a retryable error (rate limits, transient failures)
RETRYABLE_ERRORS = [
    "retry", "request_limit_exceeded", "rate limit", "insufficient_quota",
    "overloaded", "429", "bad gateway", "502"
]


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimitTracker:
    """
    Tracks API rate limits and dynamically adjusts concurrency.
    
    When rate limits are hit, reduces workers.
    When processing is smooth, gradually increases workers.
    """
    
    def __init__(self, initial_workers=5, min_workers=1, max_workers=10):
        self.current_workers = initial_workers
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.rate_limit_events = deque(maxlen=20)  # Track recent rate limit events
        self.success_count = 0
        self.lock = threading.Lock()
    
    def record_rate_limit(self):
        """Record a rate limit event and potentially reduce workers."""
        with self.lock:
            self.rate_limit_events.append(datetime.now())
            
            # Count recent rate limits (last 2 minutes)
            recent_limits = sum(
                1 for event in self.rate_limit_events
                if datetime.now() - event < timedelta(minutes=2)
            )
            
            # If we're getting rate limited frequently, reduce workers
            if recent_limits >= 3 and self.current_workers > self.min_workers:
                self.current_workers = max(self.min_workers, self.current_workers - 1)
    
    def record_success(self):
        """Record successful processing and potentially increase workers."""
        with self.lock:
            self.success_count += 1
            
            # Count recent rate limits (last 5 minutes)
            recent_limits = sum(
                1 for event in self.rate_limit_events
                if datetime.now() - event < timedelta(minutes=5)
            )
            
            # If no recent rate limits and we've had some successes, increase workers
            if (recent_limits == 0 and
                self.current_workers < self.max_workers and
                self.success_count % 20 == 0):
                self.current_workers = min(self.max_workers, self.current_workers + 1)


# =============================================================================
# PDF CONVERSION
# =============================================================================

def convert_pdf_to_base64(pdf_path, dpi=300):
    """
    Convert PDF pages to base64-encoded PNG images.
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for image conversion (default 300)
    
    Returns:
        DataFrame with columns: page_num, base64_img, doc_id
    """
    # Calculate zoom level from DPI
    zoom = dpi / 72  # 72 DPI is the standard PDF resolution
    zoom_matrix = fitz.Matrix(zoom, zoom)
    
    # Open PDF
    doc = fitz.open(pdf_path)
    
    # Process each page
    pages_data = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Render page as image
        pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        pages_data.append({
            'page_num': page_num + 1,
            'base64_img': img_base64,
            'doc_id': pdf_path
        })
    
    doc.close()
    return pd.DataFrame(pages_data)


# =============================================================================
# TEXT EXTRACTION
# =============================================================================

def extract_text_from_single_image(prompt, image_data, image_index,
                                   databricks_token, databricks_url,
                                   model, rate_tracker):
    """
    Extract text from a single image using Vision AI.
    
    Implements retry logic with exponential backoff for rate limits.
    
    Args:
        prompt: Text prompt for the model
        image_data: Base64-encoded image
        image_index: Index of the image (for tracking)
        databricks_token: Authentication token
        databricks_url: Base URL for API
        model: Model name
        rate_tracker: RateLimitTracker instance
    
    Returns:
        tuple: (image_index, extracted_text or error_message)
    """
    # Create OpenAI client
    client = OpenAI(api_key=databricks_token, base_url=databricks_url)
    
    # Validate input
    if pd.isna(image_data) or image_data == "":
        return (image_index, "ERROR: Empty image")
    
    # Retry up to 3 times
    for attempt in range(3):
        try:
            # Call Vision AI model
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }
                    ]
                }]
            )
            
            # Extract result
            result = response.choices[0].message.content.strip()
            rate_tracker.record_success()
            return (image_index, result)
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if error is retryable (rate limit, transient failure)
            is_retryable = any(err in error_str for err in RETRYABLE_ERRORS)
            
            if is_retryable and attempt < 2:  # Don't retry on last attempt
                rate_tracker.record_rate_limit()
                
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                time.sleep(wait_time)
                continue
            else:
                # Non-retryable error or max retries reached
                return (image_index, f"ERROR: {str(e)}")
    
    return (image_index, "ERROR: Max retries exceeded")


def extract_text_from_images(prompt, images, databricks_token, databricks_url,
                            model, initial_workers=5, min_workers=1, max_workers=10):
    """
    Extract text from multiple images using concurrent processing with adaptive rate limiting.
    
    Args:
        prompt: Text prompt for the model
        images: pandas Series of base64-encoded images
        databricks_token: Authentication token
        databricks_url: Base URL for API
        model: Model name
        initial_workers: Starting number of concurrent workers
        min_workers: Minimum workers (fallback during rate limiting)
        max_workers: Maximum workers (cap for scaling up)
    
    Returns:
        tuple: (results_series, stats_dict)
            - results_series: pandas Series with extracted text (same index as input)
            - stats_dict: Dictionary with success/failure counts and rate
    """
    # Ensure input is a Series
    if not isinstance(images, pd.Series):
        images = pd.Series(images)
    
    # Initialize results and rate tracker
    results = pd.Series(index=images.index, dtype='object')
    rate_tracker = RateLimitTracker(initial_workers, min_workers, max_workers)
    
    # Process images in batches with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        remaining_items = list(images.items())
        
        while remaining_items:
            # Submit batch based on current worker count
            batch_size = min(rate_tracker.current_workers, len(remaining_items))
            current_batch = remaining_items[:batch_size]
            remaining_items = remaining_items[batch_size:]
            
            # Submit tasks
            futures = {
                executor.submit(
                    extract_text_from_single_image,
                    prompt, img_data, idx,
                    databricks_token, databricks_url, model, rate_tracker
                ): idx
                for idx, img_data in current_batch
            }
            
            # Collect results
            for future in as_completed(futures):
                try:
                    image_index, result = future.result()
                    results[image_index] = result
                except Exception as e:
                    idx = futures[future]
                    results[idx] = f"ERROR: {str(e)}"
            
            # Small delay between batches to avoid overwhelming the API
            if remaining_items:
                time.sleep(0.2)
    
    # Calculate statistics
    error_count = sum(1 for result in results if str(result).startswith("ERROR:"))
    success_count = len(results) - error_count
    
    stats = {
        'success': success_count,
        'failed': error_count,
        'total': len(results),
        'success_rate': (success_count / len(results) * 100) if len(results) > 0 else 0
    }
    
    return results, stats
