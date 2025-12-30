import os
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
    JOB_COMPLETED_TOTAL,
    EVENT_PROCESSING_SECONDS
)

logger = logging.getLogger(__name__)

from app.engine.utils import generate_work_key
from app.core.logging import set_trace_context, clear_trace_context

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
        t0 = time.monotonic()
        workflow = self.registry.get_workflow(task_type)
        if not workflow:
            raise ValueError(f"Unknown task type: {task_type}")

        trace_id = str(uuid.uuid4())
        set_trace_context(trace_id)
        
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
        logger.info(
            "job.submit.stored_input",
            extra={
                "trace_id": trace_id,
                "job_task_type": task_type,
                "input_key": input_key,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        
        if task_type == "SUMMARY_REPORT":
            # SUMMARY_REPORT Special Logic: Fan-out on start
            # Support two modes: direct papers data (new) or summary_report_key (legacy)
            papers = None
            
            if "papers" in params:
                # New mode: Direct papers data in parameters
                papers = params.get("papers")
                if not isinstance(papers, list):
                    raise ValueError("SUMMARY_REPORT 'papers' must be a list")
                
                # Validate papers format
                for i, p in enumerate(papers):
                    if not isinstance(p, dict):
                        raise ValueError(f"Paper at index {i} must be a dict")
                    pdf_url = p.get("pdf_url")
                    if not pdf_url or not str(pdf_url).strip():
                        raise ValueError(f"Paper at index {i} must have non-empty 'pdf_url'")
                
                # Store input data for audit/logging (optional but recommended)
                summary_report_key = f"data:summary_report_input:{trace_id}"
                summary_report_data = {
                    "papers": papers,
                    "domain": params.get("domain", ""),
                    "style": params.get("style", "academic")
                }
                await self.storage.put(summary_report_key, summary_report_data)
                logger.info(f"SUMMARY_REPORT: Stored input data to {summary_report_key}")
                
            elif "summary_report_key" in params:
                # Legacy mode: Read from storage key
                summary_report_key = params.get("summary_report_key")
                logger.info(f"SUMMARY_REPORT: Using legacy mode with key {summary_report_key}")
                
                sr_data = await self.storage.get(summary_report_key)
                if not sr_data:
                    raise ValueError(f"Invalid summary report data at {summary_report_key}")
                     
                papers = sr_data.get("papers") or []
            else:
                raise ValueError("SUMMARY_REPORT requires either 'papers' or 'summary_report_key' in parameters")
            
            if not papers:
                raise ValueError("SUMMARY_REPORT requires at least one paper")
                
            work_keys = []
            for i, p in enumerate(papers):
                if not isinstance(p, dict):
                    continue
                pdf_url = p.get("pdf_url")
                if not pdf_url:
                    continue
                
                # Generate key
                wk = generate_work_key(trace_id, i)
                work_keys.append(wk)
                
                # Save paper input
                paper_input_key = f"data:work:{wk}"
                await self.storage.put(paper_input_key, {
                    "pdf_url": pdf_url,
                    "title": p.get("title", ""),
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
            logger.info(
                "job.submit.summary_report.fanout_parser",
                extra={
                    "trace_id": trace_id,
                    "job_task_type": task_type,
                    "work_items": len(work_keys),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            
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
            logger.info(
                "job.submit.published_first_stage",
                extra={
                    "trace_id": trace_id,
                    "job_task_type": task_type,
                    "first_stage": first_stage.name,
                    "routing_key": first_stage.command_routing_key,
                    "input_key": input_key,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
        
        JOB_SUBMITTED_TOTAL.labels(task_type=task_type).inc()
        clear_trace_context()
        
        return trace_id

    async def handle_event(self, message: MessagePackage) -> None:
        t0 = time.monotonic()
        trace_id = message.header.trace_id
        set_trace_context(trace_id)
        
        context = await self.state_manager.get_context(trace_id)
        if not context:
            logger.error(f"Context not found for trace_id: {trace_id}")
            clear_trace_context()
            return

        payload = EventPayload(**message.payload)
        logger.info(
            "evt.received",
            extra={
                "trace_id": trace_id,
                "evt_sender": message.header.sender,
                "evt_task_type": message.header.task_type,
                "status": payload.status,
                "input_key": payload.input_key,
                "output_key": payload.output_key,
            },
        )
        
        if payload.status != "SUCCESS":
            await self.failure_handler.handle(message, context)
            logger.info(
                "evt.handled.failure",
                extra={
                    "trace_id": trace_id,
                    "evt_task_type": message.header.task_type,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            clear_trace_context()
            return

        # Determine handler based on task_type
        # We assume the task_type in header corresponds to the stage name
        task_type = message.header.task_type.lower()
        
        # Construct expected event key
        event_key = f"evt.{task_type}.finished"
        
        handler = self.handlers.get(event_key)
        if handler:
            start_time = time.time()
            logger.info(
                "evt.handler.selected",
                extra={
                    "trace_id": trace_id,
                    "event_key": event_key,
                    "handler": handler.__class__.__name__,
                },
            )
            # Handler errors should not cause infinite event redelivery loops.
            # If a handler raises, we log and record it as a failure record so the job can still complete.
            try:
                await handler.handle(message, context)
            except Exception as e:
                logger.error(
                    "evt.handler.exception",
                    exc_info=True,
                    extra={
                        "trace_id": trace_id,
                        "event_key": event_key,
                        "handler": handler.__class__.__name__,
                        "error": str(e),
                    },
                )
                # Best-effort: treat orchestrator-side exceptions as failures to avoid hanging jobs.
                fail_pkg = MessagePackage(
                    header=message.header,
                    payload={
                        "status": "FAIL",
                        "input_key": payload.input_key,
                        "output_key": payload.output_key,
                        "error_msg": f"orchestrator handler error: {e}",
                    },
                )
                try:
                    await self.failure_handler.handle(fail_pkg, context)
                except Exception:
                    logger.error(
                        "evt.handler.exception.failure_handler_failed",
                        exc_info=True,
                        extra={"trace_id": trace_id, "event_key": event_key},
                    )
            EVENT_PROCESSING_SECONDS.labels(handler=task_type).observe(time.time() - start_time)
            logger.info(
                "evt.handler.done",
                extra={
                    "trace_id": trace_id,
                    "event_key": event_key,
                    "handler": handler.__class__.__name__,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
        else:
            logger.warning(f"No handler found for event: {event_key}")
            logger.warning(
                "evt.handler.missing",
                extra={
                    "trace_id": trace_id,
                    "event_key": event_key,
                    "raw_task_type": message.header.task_type,
                },
            )
            
        # Check completion
        await self._check_completion(trace_id)
        clear_trace_context()

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
        # Reconcile job state transitions that might be missed due to race conditions
        # or upstream variations in stage handlers. This is intentionally idempotent.
        context = await self.state_manager.get_context(trace_id)
        if not context:
            return False
            
        if context.current_stage == "completed":
            return True

        # SUMMARY_REPORT: once all parse tasks are done (success or fail), trigger overview aggregation.
        # This is a safety net to avoid jobs getting stuck at `processing` indefinitely.
        if context.task_type == "SUMMARY_REPORT":
            all_keys = set(context.work_keys or [])
            completed = set(context.completed_work_keys or [])
            failed = set((f.work_key for f in (context.failures or [])) if context.failures else [])

            if all_keys and (completed | failed) >= all_keys and context.current_stage == "processing":
                # Build summaries from whatever successful parse artifacts we can find.
                summaries = []
                for wk in completed:
                    # Prefer the canonical SUMMARY_REPORT parse pattern.
                    parse_key_candidates = [
                        f"data:parse:data:work:{wk}",
                        # Fallback pattern when parser is fed downloader output (other workflows)
                        f"data:parse:data:download:data:work:{wk}",
                    ]
                    parse_data = None
                    for pk in parse_key_candidates:
                        try:
                            if await self.storage.exists(pk):
                                parse_data = await self.storage.get(pk)
                                break
                        except Exception:
                            continue

                    if not isinstance(parse_data, dict):
                        continue

                    meta = parse_data.get("meta") if isinstance(parse_data.get("meta"), dict) else {}
                    summaries.append(
                        {
                            "paper": {
                                "title": parse_data.get("title"),
                                "authors": [],
                                "pdf_url": meta.get("source_url"),
                            },
                            "llm_summary": parse_data.get("llm_summary", "") or "",
                        }
                    )

                if summaries:
                    overview_in_key = f"task:{trace_id}:overview_in"
                    try:
                        await self.storage.put(
                            overview_in_key,
                            {
                                "summaries": summaries,
                                "target_lang": "en",
                                "domain": context.metadata.get("domain", "") if isinstance(context.metadata, dict) else "",
                                "style": context.metadata.get("style", "academic") if isinstance(context.metadata, dict) else "academic",
                            },
                        )
                    except Exception as e:
                        logger.error(
                            "reconcile.summary_report.storage_put_overview_in_failed",
                            exc_info=True,
                            extra={"trace_id": trace_id, "overview_in_key": overview_in_key, "error": str(e)},
                        )
                        return False

                    # Move stage first so polling reflects real progress even if publish is delayed.
                    try:
                        await self.state_manager.update_context(trace_id, {"current_stage": "overview"})
                    except Exception:
                        logger.error(
                            "reconcile.summary_report.update_stage_failed",
                            exc_info=True,
                            extra={"trace_id": trace_id},
                        )
                        return False

                    # If overview tool service is not configured (common in local demo),
                    # generate a lightweight fallback overview so the job can complete.
                    if not (os.getenv("SILICONFLOW2_API_KEY") or "").strip():
                        overview_out_key = f"data:overview:{overview_in_key}"
                        overview_md = self._fallback_overview_markdown(summaries)
                        await self.storage.put(
                            overview_out_key,
                            {
                                "overview_md": overview_md,
                                "meta": {
                                    "model": "fallback",
                                    "paper_count": len(summaries),
                                    "domain": (context.metadata.get("domain", "") if isinstance(context.metadata, dict) else ""),
                                    "style": (context.metadata.get("style", "academic") if isinstance(context.metadata, dict) else "academic"),
                                },
                            },
                        )
                        await self.state_manager.update_context(trace_id, {"current_stage": "completed"})
                        JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                        logger.warning(
                            "reconcile.summary_report.overview_fallback.completed",
                            extra={"trace_id": trace_id, "overview_output_key": overview_out_key},
                        )
                        return True

                    try:
                        await self.mq.publish_command(
                            routing_key="cmd.overview.start",
                            trace_id=trace_id,
                            task_type="overview",
                            input_key=overview_in_key,
                            task_id=trace_id,
                        )
                        logger.info(
                            "reconcile.summary_report.overview_dispatched",
                            extra={"trace_id": trace_id, "overview_in_key": overview_in_key, "summaries_count": len(summaries)},
                        )
                        return False
                    except Exception:
                        logger.error(
                            "reconcile.summary_report.publish_overview_failed",
                            exc_info=True,
                            extra={"trace_id": trace_id},
                        )
                        return False

                # Nothing to summarize -> finalize to avoid infinite polling.
                await self.state_manager.update_context(trace_id, {"current_stage": "completed"})
                JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                logger.warning(
                    "reconcile.summary_report.no_summaries.completed",
                    extra={"trace_id": trace_id, "completed_count": len(completed), "failed_count": len(failed), "work_total": len(all_keys)},
                )
                return True
            # If we're already in overview stage, reconcile completion based on stored artifact presence.
            if context.current_stage == "overview":
                overview_in_key = f"task:{trace_id}:overview_in"
                overview_out_key = f"data:overview:{overview_in_key}"
                try:
                    if await self.storage.exists(overview_out_key):
                        await self.state_manager.update_context(trace_id, {"current_stage": "completed"})
                        JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                        logger.info(
                            "reconcile.summary_report.overview_output_present.completed",
                            extra={"trace_id": trace_id, "overview_output_key": overview_out_key},
                        )
                        return True
                except Exception:
                    # ignore and fall through
                    pass

                # If tool service isn't configured, produce fallback output even in overview stage.
                if not (os.getenv("SILICONFLOW2_API_KEY") or "").strip():
                    # Reuse successful parse artifacts for fallback generation.
                    summaries = []
                    for wk in set(context.completed_work_keys or []):
                        parse_key = f"data:parse:data:work:{wk}"
                        try:
                            parse_data = await self.storage.get(parse_key)
                        except Exception:
                            parse_data = None
                        if not isinstance(parse_data, dict):
                            continue
                        meta = parse_data.get("meta") if isinstance(parse_data.get("meta"), dict) else {}
                        summaries.append(
                            {
                                "paper": {"title": parse_data.get("title"), "authors": [], "pdf_url": meta.get("source_url")},
                                "llm_summary": parse_data.get("llm_summary", "") or "",
                            }
                        )
                    if summaries:
                        overview_md = self._fallback_overview_markdown(summaries)
                        await self.storage.put(
                            overview_out_key,
                            {
                                "overview_md": overview_md,
                                "meta": {"model": "fallback", "paper_count": len(summaries)},
                            },
                        )
                    await self.state_manager.update_context(trace_id, {"current_stage": "completed"})
                    JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                    logger.warning(
                        "reconcile.summary_report.overview_fallback_in_overview.completed",
                        extra={"trace_id": trace_id, "overview_output_key": overview_out_key},
                    )
                    return True
            
        return False

    def _fallback_overview_markdown(self, summaries: list[dict]) -> str:
        # Lightweight deterministic fallback: keep headings compatible with overview_service validation.
        lines = []
        lines.append("## Background")
        lines.append("This overview was generated using a local fallback (no SILICONFLOW2_API_KEY configured).")
        lines.append("")
        lines.append("## Key Themes")
        for item in summaries[:20]:
            if not isinstance(item, dict):
                continue
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            title = (paper.get("title") or "N/A") if isinstance(paper, dict) else "N/A"
            llm_summary = (item.get("llm_summary") or "").strip()
            llm_summary = llm_summary[:800] + ("…" if len(llm_summary) > 800 else "")
            lines.append(f"- **{title}**: {llm_summary or 'N/A'}")
        lines.append("")
        lines.append("## Open Problems")
        lines.append("- N/A (fallback mode does not infer open problems).")
        lines.append("")
        lines.append("## References")
        for item in summaries[:50]:
            if not isinstance(item, dict):
                continue
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            title = (paper.get("title") or "").strip() if isinstance(paper.get("title"), str) else ""
            pdf_url = (paper.get("pdf_url") or "").strip() if isinstance(paper.get("pdf_url"), str) else ""
            if title or pdf_url:
                lines.append(f"- {title or 'N/A'} ({pdf_url or 'N/A'})")
        return "\n".join(lines).strip() + "\n"
