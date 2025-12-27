import logging
from typing import Protocol, List, Any, Dict, Optional
from app.models.messages import MessagePackage, EventPayload
from app.models.state_models import JobContext, FailureRecord
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StorageBackend, StateManager
from app.engine.utils import infer_work_key, work_has_pdf_candidate, generate_work_key
from app.core.config import get_settings
from app.infrastructure.metrics import JOB_COMPLETED_TOTAL

logger = logging.getLogger(__name__)

class EventHandler(Protocol):
    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        ...

class DiscoveryFinishedHandler:
    def __init__(self, mq: MQManager, storage: StorageBackend, state: StateManager):
        self.mq = mq
        self.storage = storage
        self.state = state
        self.settings = get_settings()

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        
        if payload.status != "SUCCESS":
            logger.error(f"Discovery failed: {payload.error_msg}")
            # Could trigger FailureHandler logic or just log
            return

        if not payload.output_key:
            logger.error("Discovery finished but no output key")
            return
            
        data = await self.storage.get(payload.output_key)
        
        # Extract results from dict or list
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict):
            results = data.get("results")
        else:
            results = None

        if not results or not isinstance(results, list):
            logger.error(f"Invalid discovery results: type={type(data)}")
            return

        valid_works = []
        work_keys = []
        
        for i, work in enumerate(results):
            if work_has_pdf_candidate(work):
                valid_works.append(work)
                # Generate key
                key = generate_work_key(context.trace_id, i)
                work_keys.append(key)
                
        if not valid_works:
            logger.info("No valid works found after discovery")
            await self.state.update_context(context.trace_id, {"current_stage": "completed"})
            JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
            return

        # Update context
        await self.state.update_context(context.trace_id, {
            "work_keys": work_keys,
            "current_stage": "processing"
        })
        
        # Publish commands
        for work, key in zip(valid_works, work_keys):
            work_input_key = f"data:work:{key}"
            # Wrap work in a dict to match Tool Service expectation (and nexus_service/core.py)
            await self.storage.put(work_input_key, {"work": work})
            
            await self.mq.publish_command(
                routing_key="cmd.downloader.start",
                trace_id=context.trace_id,
                task_type="downloader",
                input_key=work_input_key,
                task_id=key
            )

class DownloaderFinishedHandler:
    def __init__(self, mq: MQManager):
        self.mq = mq

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return 

        try:
            work_key = infer_work_key(payload.input_key or "")
        except ValueError:
            work_key = payload.input_key

        await self.mq.publish_command(
            routing_key="cmd.parser.start",
            trace_id=context.trace_id,
            task_type="parser",
            input_key=payload.output_key, # File location
            task_id=work_key
        )
        
class ParserFinishedHandler:
    def __init__(self, mq: MQManager, state: StateManager, storage: StorageBackend):
        self.mq = mq
        self.state = state
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return

        work_key = None
        if not work_key:
            try:
                work_key = infer_work_key(payload.input_key or "")
            except ValueError:
                work_key = payload.input_key

        if context.task_type == "MORNING_REPORT":
             await self.mq.publish_command(
                routing_key="cmd.indexer.start",
                trace_id=context.trace_id,
                task_type="indexer",
                input_key=payload.output_key, # Parsed data location
                task_id=work_key
            )
        elif context.task_type == "SUMMARY_REPORT":
            # Aggregation Logic
            current_ctx = await self.state.get_context(context.trace_id)
            if not current_ctx: return

            completed = set(current_ctx.completed_work_keys)
            completed.add(work_key)
            await self.state.update_context(context.trace_id, {"completed_work_keys": list(completed)})
            
            # Check for completion
            all_keys = set(current_ctx.work_keys)
            failures = set(f.work_key for f in current_ctx.failures)
            
            if (completed | failures) >= all_keys:
                # Trigger Overview
                summaries = []
                for wk in completed:
                    # Reconstruct parse output key: data:parse:{input_key}
                    # input_key was data:work:{wk}
                    parse_key = f"data:parse:data:work:{wk}"
                    parse_data = await self.storage.get(parse_key)
                    if not parse_data: continue
                    
                    summaries.append({
                        "paper": {
                            "title": parse_data.get("title"),
                            "authors": [],
                            "pdf_url": parse_data.get("meta", {}).get("source_url")
                        },
                        "llm_summary": parse_data.get("llm_summary", "")
                    })
                
                if summaries:
                    overview_in_key = f"task:{context.trace_id}:overview_in"
                    await self.storage.put(overview_in_key, {
                        "summaries": summaries,
                        "target_lang": "en",
                        "domain": context.metadata.get("domain", ""),
                        "style": context.metadata.get("style", "academic")
                    })
                    
                    await self.mq.publish_command(
                        routing_key="cmd.overview.start",
                        trace_id=context.trace_id,
                        task_type="overview",
                        input_key=overview_in_key,
                        task_id=context.trace_id
                    )

class OverviewFinishedHandler:
    def __init__(self, state: StateManager):
        self.state = state

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS": return
        
        await self.state.update_context(context.trace_id, {"current_stage": "completed"})
        JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()

class IndexerFinishedHandler:
    def __init__(self, mq: MQManager, state: StateManager, storage: StorageBackend):
        self.mq = mq
        self.state = state
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return

        try:
            work_key = infer_work_key(payload.output_key or "")
        except ValueError as e:
            logger.warning(f"Could not infer work key from {payload.output_key}: {e}")
            return
        
        # Atomic update for completed keys
        def update_fn(ctx: JobContext) -> Dict[str, Any]:
            completed = set(ctx.completed_work_keys)
            completed.add(work_key)
            return {"completed_work_keys": list(completed)}

        updated_ctx = await self.state.atomic_update_context(context.trace_id, update_fn)
        
        # Check if all done
        all_keys = set(updated_ctx.work_keys)
        failures = set(f.work_key for f in updated_ctx.failures)
        completed = set(updated_ctx.completed_work_keys)
        
        is_complete = (completed | failures) >= all_keys
        
        if is_complete and updated_ctx.current_stage != "completed":
            
            # Generate Report
            if context.task_type == "MORNING_REPORT":
                from app.services.report_service import ReportService
                report_service = ReportService(self.storage, self.state)
                try:
                    await report_service.build_morning_report(context.trace_id)
                    logger.info(f"Generated MORNING_REPORT for {context.trace_id}")
                except Exception as e:
                    logger.error(f"Failed to generate report: {e}")

            # Atomic update status
            def update_status(ctx: JobContext) -> Dict[str, Any]:
                if ctx.current_stage != "completed":
                    return {"current_stage": "completed"}
                return {}
            
            await self.state.atomic_update_context(context.trace_id, update_status)
            JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()

class FailureHandler:
    def __init__(self, state: StateManager, mq: MQManager, storage: StorageBackend):
        self.state = state
        self.mq = mq
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        payload = EventPayload(**message.payload)
        try:
            work_key = infer_work_key(payload.input_key or "")
        except ValueError:
            work_key = "unknown"
        
        failure = FailureRecord(
            work_key=work_key,
            stage=message.header.task_type,
            routing_key=message.header.sender,
            input_key=payload.input_key or "",
            error_msg=payload.error_msg or "Unknown error"
        )
        
        # Atomic update for failures
        def update_fn(ctx: JobContext) -> Dict[str, Any]:
            failures = ctx.failures
            failures.append(failure)
            return {"failures": failures}
            
        updated_ctx = await self.state.atomic_update_context(context.trace_id, update_fn)

        # Check completion
        completed = set(updated_ctx.completed_work_keys)
        failed_keys = set(f.work_key for f in updated_ctx.failures)
        all_keys = set(updated_ctx.work_keys)

        if (completed | failed_keys) >= all_keys:
            if context.task_type == "SUMMARY_REPORT":
                # Trigger Overview with partial results
                summaries = []
                for wk in completed:
                    parse_key = f"data:parse:data:work:{wk}"
                    parse_data = await self.storage.get(parse_key)
                    if not parse_data: continue
                    summaries.append({
                        "paper": {
                            "title": parse_data.get("title"),
                            "authors": [],
                            "pdf_url": parse_data.get("meta", {}).get("source_url")
                        },
                        "llm_summary": parse_data.get("llm_summary", "")
                    })
                
                if summaries:
                    overview_in_key = f"task:{context.trace_id}:overview_in"
                    await self.storage.put(overview_in_key, {
                        "summaries": summaries,
                        "target_lang": "en",
                        "domain": context.metadata.get("domain", ""),
                        "style": context.metadata.get("style", "academic")
                    })
                    await self.mq.publish_command(
                        routing_key="cmd.overview.start",
                        trace_id=context.trace_id,
                        task_type="overview",
                        input_key=overview_in_key,
                        task_id=context.trace_id
                    )
            elif updated_ctx.current_stage != "completed":
                # Generate Report for MORNING_REPORT even if failures occurred
                if context.task_type == "MORNING_REPORT":
                    from app.services.report_service import ReportService
                    report_service = ReportService(self.storage, self.state)
                    try:
                        await report_service.build_morning_report(context.trace_id)
                        logger.info(f"Generated MORNING_REPORT (with failures) for {context.trace_id}")
                    except Exception as e:
                        logger.error(f"Failed to generate report: {e}")

                # Atomic update status
                def update_status(ctx: JobContext) -> Dict[str, Any]:
                    if ctx.current_stage != "completed":
                        return {"current_stage": "completed"}
                    return {}
                
                await self.state.atomic_update_context(context.trace_id, update_status)
                JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
