import logging
from typing import Dict, Any, List, Optional
from app.infrastructure.storage import StateManager, StorageBackend
from app.models.state_models import JobContext

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, storage: StorageBackend, state_manager: StateManager):
        self.storage = storage
        self.state_manager = state_manager

    async def build_morning_report(self, trace_id: str) -> Dict[str, Any]:
        context = await self.state_manager.get_context(trace_id)
        if not context:
            raise ValueError(f"Context not found for trace_id: {trace_id}")

        report = {
            "trace_id": trace_id,
            "task_type": context.task_type,
            "requested_limit": context.requested_limit,
            "paper_count": len(context.completed_work_keys),
            "failure_count": len(context.failures),
            "papers": [],
            "failures": [f.model_dump() for f in context.failures],
            "metadata": context.metadata
        }

        for work_key in context.completed_work_keys:
            entry = await self._construct_paper_entry(work_key)
            if entry:
                report["papers"].append(entry)

        # Save report
        report_key = f"data:report:{trace_id}"
        await self.storage.put(report_key, report)
        
        # Update context with report key
        await self.state_manager.update_context(trace_id, {"report_key": report_key})
        
        return report

    async def _construct_paper_entry(self, work_key: str) -> Optional[Dict[str, Any]]:
        # Reconstruct keys based on pipeline flow:
        # Work -> Downloader -> Parser -> Indexer
        work_in_key = f"data:work:{work_key}"
        download_out_key = f"data:download:{work_in_key}"
        parse_out_key = f"data:parse:{download_out_key}"
        index_out_key = f"data:index:{parse_out_key}"

        # 1. Work metadata
        work_data = await self.storage.get(work_in_key)
        # Unwrap if necessary (handlers wrap it in {"work": ...})
        if isinstance(work_data, dict) and "work" in work_data:
            work_data = work_data["work"]
        
        # 2. Download metadata
        download_data = await self.storage.get(download_out_key)
        
        # 3. Parse data
        parse_data = await self.storage.get(parse_out_key)
        
        # 4. Index data
        index_data = await self.storage.get(index_out_key)

        if not work_data and not download_data:
            logger.warning(f"Missing base data for key: {work_key}")
            return None

        entry = {
            "paper": work_data or {}, 
            "summary": parse_data or {},
            "index": index_data or {},
            "keys": {
                "work_key": work_key,
                "download_key": download_out_key,
                "parse_key": parse_out_key,
                "index_key": index_out_key
            }
        }
        
        if download_data:
            entry["download_info"] = download_data
        
        return entry
