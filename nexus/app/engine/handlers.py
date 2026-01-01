import asyncio
import logging
import time
from typing import Protocol, List, Any, Dict, Optional
import httpx
from app.models.messages import MessagePackage, EventPayload
from app.models.state_models import JobContext, FailureRecord
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StorageBackend
from app.infrastructure.state_db import DBStateManager
from app.engine.utils import infer_work_key, work_has_pdf_candidate, generate_work_key
from app.core.config import get_settings
from app.infrastructure.metrics import JOB_COMPLETED_TOTAL

logger = logging.getLogger(__name__)

class EventHandler(Protocol):
    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        ...

class DiscoveryFinishedHandler:
    def __init__(self, mq: MQManager, storage: StorageBackend, state: DBStateManager):
        self.mq = mq
        self.storage = storage
        self.state = state
        self.settings = get_settings()

    async def _publish_single_download_command(
        self, 
        work: Dict[str, Any], 
        work_key: str, 
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Publish a single download command with error handling.
        
        Args:
            work: Work item data
            work_key: Generated work key
            trace_id: Trace ID for the job
            
        Returns:
            Dict with success status, work_key, and optional error message
        """
        try:
            pdf_url = str(work.get("pdf_url") or "").strip()
            if not pdf_url:
                raise ValueError("missing pdf_url")
            item_ref = {
                "service": "discovery",
                "type": "paper",
                "id": str(work.get("canonical_id") or work.get("openalex_id") or work_key),
                "version": "v1",
                "fetch": {"url": pdf_url},
            }
            # Publish download command (ref-only)
            await self.mq.publish_command(
                routing_key="cmd.downloader.start",
                trace_id=trace_id,
                task_type="downloader",
                input_ref=item_ref,
                params={"url": pdf_url, "paper": work},
                task_id=work_key,
            )
            
            return {
                "success": True,
                "work_key": work_key
            }
        except Exception as e:
            logger.error(
                f"Failed to publish download command for work_key={work_key}, trace_id={trace_id}: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "work_key": work_key,
                "error": str(e)
            }

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        
        if payload.status != "SUCCESS":
            logger.error(f"Discovery failed: {payload.error_msg}")
            return

        if not isinstance(payload.result_ref, dict) or payload.result_ref.get("type") != "search_result":
            logger.error("ref-only: discovery finished but no result_ref.search_result")
            return
        result_id = str(payload.result_ref.get("id") or "").strip()
        if not result_id:
            logger.error("ref-only: discovery result_ref missing id")
            return

        # Pull minimal fields via discovery Query API (no shared storage keys)
        base = (self.settings.discovery_base_url or "http://localhost:8004").rstrip("/")
        url = f"{base}/v1/results/{result_id}/min_fields"
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(url, params={"limit": max(1, int(context.requested_limit or 5) * 3)})
            if resp.status_code >= 400:
                logger.error(f"Discovery API failed: {resp.status_code} {resp.text[:200]!r}")
                return
            data = resp.json()
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            logger.error("Discovery API returned invalid items")
            return

        valid_works = []
        work_keys = []
        
        for i, work in enumerate(items):
            if not isinstance(work, dict):
                continue
            if not str(work.get("pdf_url") or "").strip():
                continue
            valid_works.append(work)
            key = generate_work_key(context.trace_id, i)
            work_keys.append(key)
                
        if not valid_works:
            logger.info("No valid works found after discovery")
            await self.state.update_context(context.trace_id, {"current_stage": "completed"})
            JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
            logger.info(
                "stage.discovery.no_valid_works.completed",
                extra={
                    "trace_id": context.trace_id,
                    "task_type": context.task_type,
                    "discovery_output_key": payload.output_key,
                    "results_count": len(results) if isinstance(results, list) else None,
                    "valid_work_count": 0,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            return

        # Update context
        def update_discovery_ctx(ctx: JobContext) -> Dict[str, Any]:
            artifacts_refs = dict(getattr(ctx, "artifacts_refs", {}) or {})
            artifacts_refs["search_results"] = payload.result_ref
            # also persist per-work meta for downstream stages
            meta = dict(ctx.metadata or {}) if isinstance(ctx.metadata, dict) else {}
            meta["work_meta"] = {wk: w for wk, w in zip(work_keys, valid_works)}
            return {
                "work_keys": work_keys,
                "current_stage": "processing",
                "artifacts_refs": artifacts_refs,
                "metadata": meta,
            }

        await self.state.atomic_update_context(context.trace_id, update_discovery_ctx)
        logger.info(
            "stage.discovery.done",
            extra={
                "trace_id": context.trace_id,
                "task_type": context.task_type,
                "discovery_result_id": result_id,
                "results_count": len(items),
                "valid_work_count": len(valid_works),
                "work_keys_count": len(work_keys),
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        
        # Publish commands concurrently with error handling
        logger.info(
            f"Publishing {len(valid_works)} download commands for trace_id={context.trace_id}"
        )
        
        tasks = [
            self._publish_single_download_command(work, key, context.trace_id)
            for work, key in zip(valid_works, work_keys)
        ]
        
        # Execute all tasks concurrently, ensuring exceptions don't stop other tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        success_count = 0
        failed_count = 0
        failed_keys = []
        
        for result in results:
            if isinstance(result, Exception):
                # Unexpected exception from gather
                failed_count += 1
                logger.error(f"Unexpected exception in download command publishing: {result}")
            elif isinstance(result, dict):
                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
                    failed_keys.append(result.get("work_key"))
        
        # Log summary
        logger.info(
            f"Download command publishing completed for trace_id={context.trace_id}: "
            f"{success_count} succeeded, {failed_count} failed"
        )
        
        if failed_count > 0:
            logger.warning(
                f"Failed to publish download commands for work_keys: {failed_keys}, "
                f"trace_id={context.trace_id}. These tasks will not be processed."
            )
        logger.info(
            "stage.downloader.fanout.published",
            extra={
                "trace_id": context.trace_id,
                "task_type": context.task_type,
                "published_total": len(valid_works),
                "publish_succeeded": success_count,
                "publish_failed": failed_count,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )

class DownloaderFinishedHandler:
    def __init__(self, mq: MQManager):
        self.mq = mq

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return 
        work_key = payload.work_key or ""
        if not work_key:
            logger.warning("downloader.finished missing work_key")
            return

        # find paper meta from context
        paper = {}
        if isinstance(context.metadata, dict):
            wm = context.metadata.get("work_meta") or {}
            if isinstance(wm, dict):
                paper = wm.get(work_key) or {}

        await self.mq.publish_command(
            routing_key="cmd.parser.start",
            trace_id=context.trace_id,
            task_type="parser",
            input_ref=payload.result_ref,
            params={"paper": paper},
            task_id=work_key,
        )
        logger.info(
            "stage.downloader.done.dispatched_parser",
            extra={
                "trace_id": context.trace_id,
                "task_type": context.task_type,
                "work_key": work_key,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        
class ParserFinishedHandler:
    def __init__(self, mq: MQManager, state: DBStateManager, storage: StorageBackend):
        self.mq = mq
        self.state = state
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return
        work_key = payload.work_key or ""
        if not work_key:
            logger.error("ParserFinishedHandler: missing work_key")
            return

        paper = {}
        if isinstance(context.metadata, dict):
            wm = context.metadata.get("work_meta") or {}
            if isinstance(wm, dict):
                paper = wm.get(work_key) or {}

        if context.task_type == "MORNING_REPORT":
            await self.mq.publish_command(
                routing_key="cmd.indexer.start",
                trace_id=context.trace_id,
                task_type="indexer",
                input_ref=payload.result_ref,
                params={"paper": paper},
                task_id=work_key,
            )
            logger.info(
                "stage.parser.done.dispatched_indexer",
                extra={
                    "trace_id": context.trace_id,
                    "task_type": context.task_type,
                    "work_key": work_key,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
        elif context.task_type == "SUMMARY_REPORT":
            # Aggregation Logic (atomic to avoid race conditions)
            def update_completed_and_artifacts(ctx: JobContext) -> Dict[str, Any]:
                completed = set(ctx.completed_work_keys)
                completed.add(work_key)

                artifacts_refs = dict(getattr(ctx, "artifacts_refs", {}) or {})
                if isinstance(payload.result_ref, dict):
                    artifacts_refs[f"parse:{work_key}"] = payload.result_ref

                return {"completed_work_keys": list(completed), "artifacts_refs": artifacts_refs}

            updated_ctx = await self.state.atomic_update_context(context.trace_id, update_completed_and_artifacts)

            all_keys = set(updated_ctx.work_keys or [])
            completed = set(updated_ctx.completed_work_keys or [])
            failures = set(f.work_key for f in (updated_ctx.failures or []))

            if all_keys and (completed | failures) >= all_keys and updated_ctx.current_stage == "processing":
                logger.info(
                    "stage.parser.summary_report.all_parsed.trigger_overview",
                    extra={
                        "trace_id": context.trace_id,
                        "task_type": context.task_type,
                        "work_total": len(all_keys),
                        "completed_count": len(completed),
                        "failed_count": len(failures),
                    },
                )

                summaries = []
                for wk in completed:
                    pref = (getattr(updated_ctx, "artifacts_refs", {}) or {}).get(f"parse:{wk}")
                    if not (isinstance(pref, dict) and pref.get("type") == "parsed_doc" and pref.get("id")):
                        continue
                    doc_id = str(pref.get("id"))
                    # Ref-only: fetch parsed via parser Query API
                    pbase = (self.settings.parser_base_url or "http://localhost:8031").rstrip("/")
                    purl = f"{pbase}/v1/parsed/{doc_id}"
                    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                        pr = await client.get(purl)
                        if pr.status_code >= 400:
                            continue
                        pdata = pr.json()
                    parse_data = pdata.get("data") if isinstance(pdata, dict) else None
                    if not isinstance(parse_data, dict):
                        continue
                    meta = parse_data.get("meta") if isinstance(parse_data.get("meta"), dict) else {}
                    # Our parser_service doesn't generate llm_summary; build a lightweight surrogate.
                    chunks = parse_data.get("chunks") or []
                    text = ""
                    if isinstance(chunks, list) and chunks:
                        first = chunks[0] if isinstance(chunks[0], dict) else {}
                        text = str(first.get("text") or "")[:800]
                    summaries.append(
                        {
                            "paper": {
                                "title": (context.metadata.get("work_meta", {}).get(wk, {}).get("title") if isinstance(context.metadata, dict) else None),
                                "authors": [],
                                "pdf_url": (context.metadata.get("work_meta", {}).get(wk, {}).get("pdf_url") if isinstance(context.metadata, dict) else None),
                            },
                            "llm_summary": text,
                        }
                    )

                if summaries:
                    # Mark stage transition (idempotent)
                    await self.state.update_context(context.trace_id, {"current_stage": "overview"})

                    await self.mq.publish_command(
                        routing_key="cmd.overview.start",
                        trace_id=context.trace_id,
                        task_type="overview",
                        input_ref={"service": "nexus", "type": "job", "id": context.trace_id, "version": "v1"},
                        params={
                            "summaries": summaries,
                            "target_lang": "en",
                            "domain": context.metadata.get("domain", "") if isinstance(context.metadata, dict) else "",
                            "style": context.metadata.get("style", "academic") if isinstance(context.metadata, dict) else "academic",
                        },
                        task_id=context.trace_id,
                    )
                    logger.info(
                        "stage.overview.dispatched",
                        extra={
                            "trace_id": context.trace_id,
                            "task_type": context.task_type,
                            "summaries_count": len(summaries),
                            "duration_ms": int((time.monotonic() - t0) * 1000),
                        },
                    )
                else:
                    # No summaries means we cannot produce overview; finalize to avoid infinite polling
                    await self.state.update_context(context.trace_id, {"current_stage": "completed"})
                    JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                    logger.warning(
                        "stage.parser.summary_report.no_summaries.completed",
                        extra={
                            "trace_id": context.trace_id,
                            "task_type": context.task_type,
                            "work_total": len(all_keys),
                            "completed_count": len(completed),
                            "failed_count": len(failures),
                            "duration_ms": int((time.monotonic() - t0) * 1000),
                        },
                    )
            else:
                logger.info(
                    "stage.parser.summary_report.partial_progress",
                    extra={
                        "trace_id": context.trace_id,
                        "task_type": context.task_type,
                        "work_total": len(all_keys),
                        "completed_count": len(completed),
                        "failed_count": len(failures),
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    },
                )

class OverviewFinishedHandler:
    def __init__(self, state: DBStateManager):
        self.state = state

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS": return
        
        await self.state.update_context(context.trace_id, {"current_stage": "completed"})
        JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
        logger.info(
            "stage.overview.done.completed",
            extra={
                "trace_id": context.trace_id,
                "task_type": context.task_type,
                "overview_output_key": payload.output_key,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )

class IndexerFinishedHandler:
    def __init__(self, mq: MQManager, state: DBStateManager, storage: StorageBackend):
        self.mq = mq
        self.state = state
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        if payload.status != "SUCCESS":
            return

        work_key = (payload.work_key or "").strip()
        if not work_key:
            logger.warning("indexer.finished missing work_key")
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
            # Ref-only: do not generate storage-key-based manifests here.
            await self.state.atomic_update_context(context.trace_id, lambda ctx: {"current_stage": "completed"})
            JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
        else:
            logger.info(
                "stage.indexer.partial_progress",
                extra={
                    "trace_id": context.trace_id,
                    "task_type": context.task_type,
                    "work_total": len(all_keys),
                    "completed_count": len(completed),
                    "failed_count": len(failures),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )

class FailureHandler:
    def __init__(self, state: DBStateManager, mq: MQManager, storage: StorageBackend):
        self.state = state
        self.mq = mq
        self.storage = storage

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        t0 = time.monotonic()
        payload = EventPayload(**message.payload)
        work_key = (payload.work_key or "").strip() or "unknown"
        
        failure = FailureRecord(
            work_key=work_key,
            stage=message.header.task_type,
            routing_key=message.header.sender,
            input_key="",  # ref-only
            error_msg=payload.error_msg or "Unknown error"
        )
        
        # Atomic update for failures
        def update_fn(ctx: JobContext) -> Dict[str, Any]:
            # Create new list to avoid side effects on cached context
            new_failures = list(ctx.failures)
            new_failures.append(failure)
            return {"failures": new_failures}
            
        updated_ctx = await self.state.atomic_update_context(context.trace_id, update_fn)
        logger.warning(
            "stage.failed.recorded",
            extra={
                "trace_id": context.trace_id,
                "task_type": context.task_type,
                "stage": message.header.task_type,
                "work_key": work_key,
                "error_msg": payload.error_msg,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )

        # Check completion
        completed = set(updated_ctx.completed_work_keys)
        failed_keys = set(f.work_key for f in updated_ctx.failures)
        all_keys = set(updated_ctx.work_keys)

        if (completed | failed_keys) >= all_keys:
            if context.task_type == "SUMMARY_REPORT":
                # If overview itself failed, don't loop forever: finalize with failures.
                if str(message.header.task_type or "").lower() == "overview":
                    await self.state.update_context(context.trace_id, {"current_stage": "completed"})
                    JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                    logger.warning(
                        "stage.overview.failed.completed",
                        extra={
                            "trace_id": context.trace_id,
                            "task_type": context.task_type,
                            "completed_count": len(completed),
                            "failed_count": len(failed_keys),
                            "work_total": len(all_keys),
                        },
                    )
                    return
                # Trigger Overview with partial results (ref-only: via parser Query API + params)
                summaries: List[Dict[str, Any]] = []
                refs = getattr(updated_ctx, "artifacts_refs", {}) or {}
                pbase = (self.settings.parser_base_url or "http://localhost:8031").rstrip("/")
                wm = (context.metadata.get("work_meta") if isinstance(context.metadata, dict) else {}) or {}
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    for wk in completed:
                        pref = refs.get(f"parse:{wk}") if isinstance(refs, dict) else None
                        if not (isinstance(pref, dict) and pref.get("type") == "parsed_doc" and pref.get("id")):
                            continue
                        doc_id = str(pref.get("id"))
                        pr = await client.get(f"{pbase}/v1/parsed/{doc_id}")
                        if pr.status_code >= 400:
                            continue
                        pdata = pr.json()
                        doc = pdata.get("data") if isinstance(pdata, dict) else None
                        if not isinstance(doc, dict):
                            continue
                        chunks = doc.get("chunks") or []
                        text = ""
                        if isinstance(chunks, list) and chunks:
                            c0 = chunks[0] if isinstance(chunks[0], dict) else {}
                            text = str(c0.get("text") or "")[:800]
                        meta = wm.get(wk) if isinstance(wm, dict) else {}
                        if not isinstance(meta, dict):
                            meta = {}
                        summaries.append(
                            {
                                "paper": {
                                    "title": meta.get("title"),
                                    "authors": meta.get("authors") or [],
                                    "pdf_url": meta.get("pdf_url"),
                                },
                                "llm_summary": text,
                            }
                        )

                if summaries:
                    await self.state.update_context(context.trace_id, {"current_stage": "overview"})
                    await self.mq.publish_command(
                        routing_key="cmd.overview.start",
                        trace_id=context.trace_id,
                        task_type="overview",
                        input_ref={"service": "nexus", "type": "job", "id": context.trace_id, "version": "v1"},
                        params={
                            "summaries": summaries,
                            "target_lang": "en",
                            "domain": context.metadata.get("domain", "") if isinstance(context.metadata, dict) else "",
                            "style": context.metadata.get("style", "academic") if isinstance(context.metadata, dict) else "academic",
                        },
                        task_id=context.trace_id,
                    )
                    logger.info(
                        "stage.failure.summary_report.trigger_overview",
                        extra={
                            "trace_id": context.trace_id,
                            "task_type": context.task_type,
                            "summaries_count": len(summaries),
                        },
                    )
                else:
                    # Nothing to summarize; finalize to avoid infinite polling
                    await self.state.update_context(context.trace_id, {"current_stage": "completed"})
                    JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
                    logger.warning(
                        "stage.failure.summary_report.no_summaries.completed",
                        extra={
                            "trace_id": context.trace_id,
                            "task_type": context.task_type,
                            "completed_count": len(completed),
                            "failed_count": len(failed_keys),
                            "work_total": len(all_keys),
                        },
                    )
            elif updated_ctx.current_stage != "completed":
                # Ref-only: finalize; no storage-key-based manifests.
                await self.state.atomic_update_context(context.trace_id, lambda ctx: {"current_stage": "completed"})
                JOB_COMPLETED_TOTAL.labels(task_type=context.task_type, status="success").inc()
