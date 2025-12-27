import uuid
import logging
import time
from typing import Dict, Optional, Type
from app.models.messages import MessagePackage, EventPayload
from app.models.state_models import JobContext
from app.models.workflow_models import WorkflowDefinition
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StateManager, StorageBackend
from app.engine.workflows import WorkflowRegistry
from app.engine.handlers import (
    EventHandler,
    DiscoveryFinishedHandler,
    DownloaderFinishedHandler,
    ParserFinishedHandler,
    IndexerFinishedHandler,
    FailureHandler
)
from app.core.config import get_settings
from app.infrastructure.metrics import (
    JOB_SUBMITTED_TOTAL, 
    EVENT_PROCESSING_SECONDS
)

logger = logging.getLogger(__name__)

from app.engine.utils import generate_work_key

class WorkflowOrchestrator:
    def __init__(
        self, 
        mq: MQManager, 
        state_manager: StateManager, 
        storage: StorageBackend,
        registry: WorkflowRegistry
    ):
        self.mq = mq
        self.state_manager = state_manager
        self.storage = storage
        self.registry = registry
        self.settings = get_settings()
        
        # Initialize handlers
        # Map event keys to handlers
        from app.engine.handlers import (
            DiscoveryFinishedHandler,
            DownloaderFinishedHandler,
            ParserFinishedHandler,
            IndexerFinishedHandler,
            OverviewFinishedHandler
        )
        self.handlers: Dict[str, EventHandler] = {
            "evt.discovery.finished": DiscoveryFinishedHandler(mq, storage, state_manager),
            "evt.downloader.finished": DownloaderFinishedHandler(mq),
            "evt.parser.finished": ParserFinishedHandler(mq, state_manager, storage),
            "evt.indexer.finished": IndexerFinishedHandler(mq, state_manager, storage),
            "evt.overview.finished": OverviewFinishedHandler(state_manager),
        }
        self.failure_handler = FailureHandler(state_manager, mq, storage)

    async def submit_job(self, task_type: str, params: Dict) -> str:
        workflow = self.registry.get_workflow(task_type)
        if not workflow:
            raise ValueError(f"Unknown task type: {task_type}")

        trace_id = str(uuid.uuid4())
        
        context = JobContext(
            trace_id=trace_id,
            task_type=task_type,
            init_key=f"job:{trace_id}:init",
            requested_limit=params.get("limit", 5),
            metadata=params
        )
        
        # Input key
        input_key = f"data:job:{trace_id}:input"
        await self.storage.put(input_key, params)
        
        if task_type == "SUMMARY_REPORT":
            # SUMMARY_REPORT Special Logic: Fan-out on start
            summary_report_key = params.get("summary_report_key")
            if not summary_report_key:
                raise ValueError("SUMMARY_REPORT requires summary_report_key")
            
            sr_data = await self.storage.get(summary_report_key)
            print(f"DEBUG: Orchestrator sr_data type={type(sr_data)} val={sr_data}")
            if not sr_data:
                raise ValueError(f"Invalid summary report data at {summary_report_key}")
                 
            papers = sr_data.get("papers") or []
            if not papers:
                raise ValueError("No papers in summary report")
                
            work_keys = []
            for i, p in enumerate(papers):
                if not isinstance(p, dict): continue
                pdf_url = p.get("pdf_url")
                if not pdf_url: continue
                
                # Generate key
                wk = generate_work_key(trace_id, i)
                work_keys.append(wk)
                
                # Save paper input
                paper_input_key = f"data:work:{wk}"
                await self.storage.put(paper_input_key, {
                    "pdf_url": pdf_url,
                    "title": p.get("title"),
                    "authors": p.get("authors") or [],
                    "source_url": pdf_url,
                    "content_type": "application/pdf"
                })
                
                # Dispatch to Parser directly (as per workflow)
                await self.mq.publish_command(
                    routing_key="cmd.parser.start",
                    trace_id=trace_id,
                    task_type="parser",
                    input_key=paper_input_key,
                    task_id=wk
                )
            
            context.work_keys = work_keys
            context.current_stage = "processing"
            await self.state_manager.save_context(context)
            logger.info(f"Started SUMMARY_REPORT {trace_id} with {len(work_keys)} papers")
            
        else:
            # Standard Linear/Discovery Start
            await self.state_manager.save_context(context)
            
            # Determine first stage
            first_stage = workflow.stages[0]
            if workflow.initial_stage:
                for s in workflow.stages:
                    if s.name == workflow.initial_stage:
                        first_stage = s
                        break
            
            # Publish command
            await self.mq.publish_command(
                routing_key=first_stage.command_routing_key,
                trace_id=trace_id,
                task_type=first_stage.name,
                input_key=input_key,
                task_id=trace_id,
                params=params
            )
            
            await self.state_manager.update_context(trace_id, {"current_stage": first_stage.name})
        
        JOB_SUBMITTED_TOTAL.labels(task_type=task_type).inc()
        
        return trace_id

    async def handle_event(self, message: MessagePackage) -> None:
        trace_id = message.header.trace_id
        
        context = await self.state_manager.get_context(trace_id)
        if not context:
            logger.error(f"Context not found for trace_id: {trace_id}")
            return

        payload = EventPayload(**message.payload)
        
        if payload.status != "SUCCESS":
            await self.failure_handler.handle(message, context)
            return

        # Determine handler based on task_type
        # We assume the task_type in header corresponds to the stage name
        task_type = message.header.task_type.lower()
        
        # Construct expected event key
        event_key = f"evt.{task_type}.finished"
        
        handler = self.handlers.get(event_key)
        if handler:
            start_time = time.time()
            await handler.handle(message, context)
            EVENT_PROCESSING_SECONDS.labels(handler=task_type).observe(time.time() - start_time)
        else:
            logger.warning(f"No handler found for event: {event_key}")
            
        # Check completion
        await self._check_completion(trace_id)

    async def get_job_status(self, trace_id: str) -> Optional[JobContext]:
        return await self.state_manager.get_context(trace_id)

    def _determine_next_stage(self, current_stage: str, workflow_type: str) -> Optional[str]:
        workflow = self.registry.get_workflow(workflow_type)
        if not workflow:
            return None
            
        for stage in workflow.stages:
            if stage.name == current_stage:
                return stage.next_stage
                
        return None

    async def _check_completion(self, trace_id: str) -> bool:
        # Check if job is complete
        context = await self.state_manager.get_context(trace_id)
        if not context:
            return False
            
        if context.current_stage == "completed":
            return True
            
        return False
