import requests
import time
import sys
import json

BASE_URL = "http://localhost:8000/api/v1"

def wait_for_service():
    print("Waiting for service to be healthy...")
    for _ in range(30):
        try:
            resp = requests.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                print("Service is healthy!")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    print("Service failed to become healthy.")
    return False

def run_test():
    if not wait_for_service():
        sys.exit(1)

    print("\n1. Submitting Job...")
    payload = {
        "task_type": "MORNING_REPORT",
        "parameters": {
            "query": "LLM Agents",
            "limit": 3
        }
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/jobs", json=payload)
        resp.raise_for_status()
        data = resp.json()
        trace_id = data["trace_id"]
        print(f"Job submitted! Trace ID: {trace_id}")
    except Exception as e:
        print(f"Failed to submit job: {e}")
        sys.exit(1)

    print("\n2. Polling Job Status...")
    while True:
        resp = requests.get(f"{BASE_URL}/jobs/{trace_id}")
        if resp.status_code != 200:
            print(f"Error getting status: {resp.status_code}")
            break
            
        status_data = resp.json()
        status = status_data["status"]
        completed = status_data["completed_count"]
        total = status_data["total_work_items"]
        
        print(f"Status: {status} | Progress: {completed}/{total}")
        
        if status in ["completed", "failed"]:
            print(f"\nJob finished with status: {status}")
            print(json.dumps(status_data, indent=2))
            break
            
        time.sleep(1)

if __name__ == "__main__":
    run_test()
