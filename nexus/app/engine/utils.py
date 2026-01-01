import re
from typing import Dict, Any, Optional

def infer_work_key(key: str) -> str:
    """
    Ref-only: work_key is an explicit field in messages, so we only accept the
    canonical work key format.
    
    Args:
        key: The key string to parse.
        
    Returns:
        The inferred work key.
        
    Raises:
        ValueError: If the key format is not recognized.
    """
    if not key:
        raise ValueError("Key cannot be empty")
        
    # Pattern: Direct work key (task:{trace_id}:work:{index})
    if re.match(r"^task:.+:work:.+$", key):
        return key
        
    # Special case: if key is just the index/id? No, we expect strict format.
    raise ValueError(f"Unrecognized key format: {key}")

def work_has_pdf_candidate(work_item: Dict[str, Any]) -> bool:
    """
    Checks if the work item has a valid PDF candidate.
    
    Checks best_oa_location, locations, and arXiv sources.
    
    Args:
        work_item: The work item dictionary (e.g. from OpenAlex).
        
    Returns:
        True if a PDF candidate is found, False otherwise.
    """
    def is_valid_source(loc: Dict[str, Any]) -> bool:
        # Check for explicit PDF URL
        if loc.get("pdf_url"):
            return True
            
        # Check landing page or url
        url = loc.get("landing_page_url") or loc.get("url")
        if not url:
            return False
            
        # Check for PDF extension or arXiv
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return True
        if "arxiv.org" in url_lower:
            return True
            
        return False

    # Check best_oa_location
    best_oa = work_item.get("best_oa_location")
    if best_oa and is_valid_source(best_oa):
        return True

    # Check locations
    locations = work_item.get("locations", [])
    if isinstance(locations, list):
        for loc in locations:
            if isinstance(loc, dict) and is_valid_source(loc):
                return True
                
    return False

def generate_work_key(trace_id: str, index: int) -> str:
    """
    Generates a sequential work key.
    
    Args:
        trace_id: The job trace ID.
        index: The sequence index.
        
    Returns:
        The formatted work key string.
    """
    return f"task:{trace_id}:work:{index}"
