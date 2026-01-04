import asyncio
import sys
import os
import uuid
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add nexus directory to path to allow 'app' imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus"))
# Add download service directory to path to allow 'app' imports from it
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_services", "download_service"))

# 1. Import Nexus Components
from app.core.config import Settings
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import MinIOStorage, StateManager
from app.engine.workflows import WorkflowRegistry
from app.engine.orchestrator import WorkflowOrchestrator

# 2. Import Tool Services (Existing)
from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from tool_services.download_service.nexus_tool.tool_service import DownloaderToolService
from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from tool_services.overview_service.nexus_tool.tool_service import OverviewToolService
from shared.common import MockStorage

async def main():
    print("--- 🚀 Starting Nexus (New Architecture) Demo ---")

    # Configuration
    # Ensure workflow config path is correct relative to execution or absolute
    workflow_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus", "config", "workflows.yaml")
    settings = Settings(workflow_config_path=workflow_path)
    
    # Initialize Nexus Components
    print(f"Initializing Nexus with config: {workflow_path}")
    mq_manager = MQManager(settings)
    storage = MinIOStorage(settings)
    state_manager = StateManager(storage)
    registry = WorkflowRegistry.from_yaml(settings.workflow_config_path)
    orchestrator = WorkflowOrchestrator(mq_manager, state_manager, storage, registry)

    # Initialize Tool Services
    discovery = DiscoveryToolService()
    downloader = DownloaderToolService()
    indexer = IndexerToolService()
    overview = OverviewToolService()

    try:
        # Start Services
        print("Starting Nexus Infrastructure...")
        await mq_manager.connect()
        
        # Start Nexus Consumer
        t_nexus = asyncio.create_task(
            mq_manager.start_consuming(
                queue_name=settings.event_queue,
                callback=orchestrator.handle_event
            )
        )
        
        # Start Tool Services
        print("Starting Tool Services...")
        t_discovery = asyncio.create_task(discovery.start())
        t_dl = asyncio.create_task(downloader.start())
        t_idx = asyncio.create_task(indexer.start())
        t_overview = asyncio.create_task(overview.start())

        await asyncio.sleep(2)  # Wait for connections

        # Submit Job
        print("\n--- 📥 Submitting Job ---")
        task_type = os.getenv("DEMO_TASK_TYPE", "MORNING_REPORT").strip().upper()
        
        if task_type == "SUMMARY_REPORT":
            print("Submitting SUMMARY_REPORT...")
            seed_key = f"seed:summary_report:{uuid.uuid4()}"
            await MockStorage.save(
                seed_key,
                {
                    "domain": "Graph Neural Networks",
                    "style": "academic",
                    "papers": [
                        {"pdf_url": "https://arxiv.org/pdf/2010.03409", "title": "Graph Neural Networks: A Review of Methods and Applications"},
                        {"pdf_url": "https://arxiv.org/pdf/1810.00826.pdf", "title": "Graph Attention Networks"},
                    ],
                },
            )
            # Use orchestrator directly to submit
            trace_id = await orchestrator.submit_job("SUMMARY_REPORT", {"summary_report_key": seed_key})
            print(f"Job Submitted! Trace ID: {trace_id}")
            
        else:
            print("Submitting MORNING_REPORT...")
            job_data = {
                "query": "GNN",
                "filters": {
                    "last_n_days": 365,
                    "is_oa": "true",
                },
                "limit": 5,
            }
            trace_id = await orchestrator.submit_job("MORNING_REPORT", job_data)
            print(f"Job Submitted! Trace ID: {trace_id}")

        # Wait for completion (poll state in MinIO)
        print("\n--- ⏳ Waiting for Workflow Completion (polling task:{trace_id}:ctx) ---")
        for i in range(60):  # Wait up to 60*5 = 300 seconds
            await asyncio.sleep(5)
            try:
                ctx = await state_manager.get_context(trace_id)
                if ctx:
                    print(
                        f"\n[{i}] stage={ctx.current_stage} "
                        f"done={len(ctx.completed_work_keys)}/{len(ctx.work_keys)} "
                        f"fail={len(ctx.failures)}"
                    )
                    if ctx.current_stage == "completed":
                        manifest_key = (ctx.artifacts or {}).get("detailed_manifest")
                        if manifest_key:
                            print(f"✅ Completed. detailed_manifest={manifest_key}")
                        else:
                            print("✅ Completed.")
                        break
                else:
                    print(f"\n[{i}] ctx not found yet")
            except Exception as e:
                print(f"\n[{i}] polling error: {e!r}")
            print(".", end="", flush=True)

        else:
            print("\nTimeout waiting for completion.")

    except Exception as e:
        print(f"\n[!!!] Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n--- 🛑 Stopping Demo ---")
        await mq_manager.disconnect()
        
        # NOTE: paper_analyse ParserToolService is deprecated in ref-only mode.
        # Run `tool_services/parser_service` (API + MQ worker) separately (e.g. via docker-compose) to handle cmd.parser.start.
        tasks = [t_nexus, t_discovery, t_dl, t_idx, t_overview]
        for t in tasks:
            t.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        print("--- Services Stopped Gracefully ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
