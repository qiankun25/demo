import time
import requests
import json
import sys

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
BASE_HOST = "http://localhost:8000"
POLL_INTERVAL = 5  # seconds, reduced for better feedback

def submit_job():
    """Submits a Morning Report job."""
    url = f"{API_BASE_URL}/jobs"
    payload = {
        "task_type": "MORNING_REPORT",
        "parameters": {
            "query": "Large Language Models",
            "limit": 3,  # reduced for faster testing
            "filters": {
                "last_n_days": 30
            }
        }
    }
    
    print(f"Submitting job to {url}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Job submitted successfully. Trace ID: {data['trace_id']}")
        if 'message' in data:
            print(f"Message: {data['message']}")
        return data['trace_id']
    except requests.exceptions.RequestException as e:
        print(f"Error submitting job: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response content: {e.response.text}")
        sys.exit(1)

def check_status(trace_id):
    """Checks the status of a job."""
    url = f"{API_BASE_URL}/jobs/{trace_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error checking status: {e}")
        return None

def download_artifact(artifact_url, name):
    """Downloads an artifact from the given URL."""
    # Ensure URL is absolute
    if artifact_url.startswith("/"):
        full_url = f"{BASE_HOST}{artifact_url}"
    else:
        full_url = artifact_url
        
    print(f"Downloading artifact '{name}' from {full_url}...")
    try:
        response = requests.get(full_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to download artifact {name}: {e}")
        return None

def main():
    # 1. Submit Job
    trace_id = submit_job()
    
    # 2. Poll Status
    print(f"Starting polling for job {trace_id}...")
    while True:
        status_data = check_status(trace_id)
        
        if not status_data:
            print("Failed to retrieve status. Retrying...")
            time.sleep(POLL_INTERVAL)
            continue
            
        status = status_data.get("status")
        total = status_data.get('total_work_items', 0)
        completed = status_data.get('completed_count', 0)
        failed = status_data.get('failed_count', 0)
        
        print(f"[{time.strftime('%H:%M:%S')}] Job Status: {status}")
        print(f"  Progress: {completed}/{total} completed, {failed} failed")
        
        if status == "completed":
            print("\n" + "="*50)
            print("Job Completed Successfully!")
            artifacts = status_data.get("artifacts", {})
            print("Artifacts List:")
            print(json.dumps(artifacts, indent=2))
            
            # Try to download the manifest if available
            if "detailed_manifest" in artifacts:
                manifest = download_artifact(artifacts["detailed_manifest"], "detailed_manifest")
                if manifest:
                    print("\n--- Detailed Manifest ---")
                    print(json.dumps(manifest, indent=2))
            
            print("="*50)
            break
        elif status == "failed":
            print("\n" + "="*50)
            print("Job Failed!")
            print("Failures:")
            print(json.dumps(status_data.get("failures"), indent=2))
            print("="*50)
            break
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
