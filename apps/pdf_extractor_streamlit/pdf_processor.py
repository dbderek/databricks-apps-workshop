"""
PDF Processing Module - Contains all PDF to text extraction logic
Adapted from Llama 4 PDF Parsing Notebook
"""

import base64
import fitz
import pandas as pd
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from collections import deque
from datetime import datetime, timedelta
import threading

RETRYABLE_ERROR_SUBSTRINGS = [
    "retry", "got empty embedding result", "request_limit_exceeded", 
    "rate limit", "insufficient_quota", "expecting value", "rate", 
    "overloaded", "429", "bad gateway", "502"
]

class RateLimitTracker:
    """Track API rate limits and adjust concurrency dynamically."""
    
    def __init__(self, initial_workers=5, min_workers=1, max_workers=10):
        self.current_workers = initial_workers
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.rate_limit_events = deque(maxlen=20)
        self.success_count = 0
        self.lock = threading.Lock()
        
    def record_rate_limit(self):
        """Record a rate limit event and potentially reduce workers."""
        with self.lock:
            self.rate_limit_events.append(datetime.now())
            recent_limits = sum(
                1 for event in self.rate_limit_events 
                if datetime.now() - event < timedelta(minutes=2)
            )
            
            if recent_limits >= 3 and self.current_workers > self.min_workers:
                old_workers = self.current_workers
                self.current_workers = max(self.min_workers, self.current_workers - 1)
                return f"Rate limits detected! Reducing workers: {old_workers} → {self.current_workers}"
                
    def record_success(self):
        """Record successful processing and potentially increase workers."""
        with self.lock:
            self.success_count += 1
            recent_limits = sum(
                1 for event in self.rate_limit_events 
                if datetime.now() - event < timedelta(minutes=5)
            )
            
            if (recent_limits == 0 and 
                self.current_workers < self.max_workers and 
                self.success_count % 20 == 0):
                old_workers = self.current_workers
                self.current_workers = min(self.max_workers, self.current_workers + 1)
                return f"Performance good! Increasing workers: {old_workers} → {self.current_workers}"


def convert_pdf_to_base64(pdf_path, dpi=300, progress_callback=None):
    """
    Convert PDF to base64 images.
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution (default 300)
        progress_callback: Optional callback function(current, total, message)
    
    Returns:
        pandas DataFrame with columns: page_num, base64_img, doc_id
    """
    zoom = dpi / 72
    zoom_matrix = fitz.Matrix(zoom, zoom)
    
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    
    if progress_callback:
        progress_callback(0, num_pages, f"Processing {num_pages} pages at {dpi} DPI...")
    
    df_data = []
    
    for page_num in range(num_pages):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        df_data.append({
            'page_num': page_num + 1,
            'base64_img': img_base64,
            'doc_id': pdf_path
        })
        
        if progress_callback:
            progress_callback(page_num + 1, num_pages, f"Converted page {page_num + 1}/{num_pages}")
    
    doc.close()
    return pd.DataFrame(df_data)


def process_single_image(prompt, image_data, image_index, databricks_url, model, rate_tracker):
    """Process a single image with adaptive rate limiting."""
    
    # OpenAI client will use app's credentials automatically in Databricks Apps
    client = OpenAI(base_url=databricks_url)
    
    if pd.isna(image_data) or image_data == "":
        return (image_index, "ERROR: Empty image")
    
    for attempt in range(3):
        try:
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
            
            result = response.choices[0].message.content.strip()
            rate_tracker.record_success()
            return (image_index, result)
            
        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(substring in error_str for substring in RETRYABLE_ERROR_SUBSTRINGS)
            
            if is_retryable:
                rate_tracker.record_rate_limit()
                
                if attempt < 2:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    time.sleep(wait_time)
                    continue
                else:
                    return (image_index, f"ERROR: Rate limited after 3 attempts - {str(e)}")
            else:
                return (image_index, f"ERROR: {str(e)}")
    
    return (image_index, "ERROR: Max retries exceeded")


def process_images_adaptive(prompt, images, databricks_url,
                           model="databricks-llama-4-maverick",
                           initial_workers=5, min_workers=1, max_workers=10,
                           progress_callback=None):
    """
    Adaptive processing that adjusts concurrency based on rate limits.
    
    Args:
        prompt: Text prompt for the model
        images: pandas Series of base64 encoded image strings
        databricks_url: Base URL for Databricks API
        model: Model name to use
        initial_workers: Starting number of concurrent workers
        min_workers: Minimum workers
        max_workers: Maximum workers
        progress_callback: Optional callback function(current, total, message, stats)
        
    Returns:
        pandas Series: Results with same index as input
    """
    
    if not isinstance(images, pd.Series):
        images = pd.Series(images)
    
    results = pd.Series(index=images.index, dtype='object')
    rate_tracker = RateLimitTracker(
        initial_workers=initial_workers,
        min_workers=min_workers,
        max_workers=max_workers
    )
    
    total = len(images)
    processed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        remaining_items = list(images.items())
        
        while remaining_items:
            batch_size = min(rate_tracker.current_workers, len(remaining_items))
            current_batch = remaining_items[:batch_size]
            remaining_items = remaining_items[batch_size:]
            
            futures = {
                executor.submit(
                    process_single_image, prompt, img_data, idx,
                    databricks_url, model, rate_tracker
                ): idx
                for idx, img_data in current_batch
            }
            
            for future in as_completed(futures):
                try:
                    image_index, result = future.result()
                    results[image_index] = result
                    processed += 1
                    
                    if progress_callback:
                        stats = {
                            'workers': rate_tracker.current_workers,
                            'rate_limits': len(rate_tracker.rate_limit_events),
                            'success': not result.startswith("ERROR:")
                        }
                        progress_callback(
                            processed, total,
                            f"Processing page {image_index + 1}/{total}",
                            stats
                        )
                    
                except Exception as e:
                    idx = futures[future]
                    results[idx] = f"ERROR: Exception - {str(e)}"
                    processed += 1
            
            if remaining_items:
                time.sleep(0.2)
    
    error_count = sum(1 for result in results if str(result).startswith("ERROR:"))
    success_count = len(results) - error_count
    
    return results, {
        'success': success_count,
        'failed': error_count,
        'total': len(results),
        'success_rate': (success_count / len(results) * 100) if len(results) > 0 else 0
    }
