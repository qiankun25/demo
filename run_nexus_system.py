import asyncio
import subprocess
import sys
import os
import time
import httpx
import signal

# Configuration
NEXUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus")
TOOLS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_tools.py")
API_URL = "http://localhost:8000/api/v1"

def start_nexus():
    print("--- 🚀 Starting Nexus Service (Subprocess) ---")
    env = os.environ.copy()
    env["PYTHONPATH"] = NEXUS_DIR
    # Ensure dependencies are found (using the same venv as this script)
    
    # Run uvicorn
    # We use the full path to python to ensure we use the current venv
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    return subprocess.Popen(cmd, cwd=NEXUS_DIR, env=env)

def start_tools():
    print("--- 🛠️ Starting Tool Services (Subprocess) ---")
    cmd = [sys.executable, TOOLS_SCRIPT]
    return subprocess.Popen(cmd)

async def wait_for_nexus_health():
    print("Waiting for Nexus API to be healthy...")
    async with httpx.AsyncClient() as client:
        for i in range(30):
            try:
                # Assuming there is a health check or just check openapi
                # Default api_prefix is /api/v1, so docs are at /api/v1/docs
                resp = await client.get("http://localhost:8000/api/v1/docs")
                if resp.status_code == 200:
                    print("Nexus API is UP!")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
            print(".", end="", flush=True)
    print("\nNexus API failed to start.")
    return False

async def submit_job():
    task_type = "MORNING_REPORT" # 强制执行早报
    print(f"\n--- 📥 Submitting Job: {task_type} ---")
    
    async with httpx.AsyncClient() as client:
        if task_type == "SUMMARY_REPORT":
            # Seed data first? 
            # In the API-first approach, we might pass data directly or upload first.
            # But the legacy demo used MockStorage to seed.
            # Here we can't easily access MockStorage (in tools process).
            # BUT, we can use the `shared.common.MockStorage` in THIS process to seed MinIO!
            # Since MockStorage uses MinIO, it's shared state!
            
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from shared.common import MockStorage
            
            seed_key = f"seed:summary_report:{int(time.time())}"
            print(f"Seeding data to MinIO key: {seed_key}")
            await MockStorage.save(
                seed_key,
                {
                    "domain": "Graph Neural Networks",
                    "style": "academic",
                    "papers": [
                        {"pdf_url": "https://arxiv.org/pdf/2010.03409", "title": "Graph Neural Networks Review"},
                        {"pdf_url": "https://arxiv.org/pdf/1810.00826.pdf", "title": "GAT"},
                    ],
                },
            )
            print(f"DEBUG: MockStorage Saved to Bucket={MockStorage._bucket} Key={MockStorage._object_name(seed_key)}")
            
            payload = {
                "task_type": "SUMMARY_REPORT",
                "parameters": {"summary_report_key": seed_key}
            }
        else:
            payload = {
                "task_type": "MORNING_REPORT",
                "parameters": {
                    "query": "Large Language Models",
                    "filters": {"last_n_days": 90, "is_oa": "true"},
                    "limit": 2
                }
            }
            
        resp = await client.post(f"{API_URL}/jobs", json=payload)
        if resp.status_code != 202: # Check for 202 Accepted
            print(f"Failed to submit job: {resp.status_code} {resp.text}")
            return None
        
        data = resp.json()
        job_id = data.get("trace_id")
        print(f"Job Submitted! Trace ID: {job_id}")
        return job_id

import traceback

async def poll_job(job_id):
    print(f"\n--- ⏳ Polling Job Status: {job_id} ---")
    async with httpx.AsyncClient(timeout=30.0) as client: # 增加 timeout
        for i in range(60): # 5 mins
            try:
                resp = await client.get(f"{API_URL}/jobs/{job_id}")
                if resp.status_code == 200:
                    status_data = resp.json()
                    state = status_data.get("status") 
                    print(f"[{i}] Status: {state}")
                    
                    if state in ["completed", "success"]:
                        print("Job Completed Successfully! 🎉")
                        return
                    elif state in ["failed", "error"]:
                        print("Job Failed! ❌")
                        return
                else:
                    print(f"[{i}] API Error: {resp.status_code}")
            except Exception as e:
                print(f"[{i}] Polling Exception: {repr(e)}")
                # traceback.print_exc() # 可选
            
            await asyncio.sleep(5)

async def main():
    nexus_proc = start_nexus()
    tools_proc = start_tools()
    
    try:
        if await wait_for_nexus_health():
            job_id = await submit_job()
            if job_id:
                try:
                    await poll_job(job_id)
                except Exception as e:
                    print(f"Error polling job (outer): {e}")
                    traceback.print_exc()
        
        # Keep alive for a bit to see logs
        print("\nDemo finished. Press Ctrl+C to stop or waiting 10s...")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        pass
    finally:
        print("\n--- 🛑 Stopping Services ---")
        nexus_proc.terminate()
        tools_proc.terminate()
        
        nexus_proc.wait()
        tools_proc.wait()
        print("Services stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
