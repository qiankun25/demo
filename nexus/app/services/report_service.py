"""Service for building standardized reports from job artifacts"""

import logging
from typing import Dict, Any, Optional, List
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.report_models import (
    MorningReportResponse,
    SummaryReportResponse,
    PaperReport,
    PaperMetadata,
    PaperSummary,
    IndexInfo,
    PaperKeys,
    FailureInfo,
)
from app.models.state_models import JobContext

logger = logging.getLogger(__name__)


class ReportService:
    """Service for aggregating artifacts into standardized reports"""

    def __init__(self, orchestrator: WorkflowOrchestrator):
        self.orchestrator = orchestrator
        self.storage = orchestrator.storage
        self.state = orchestrator.state_manager

    async def build_report(self, trace_id: str) -> Dict[str, Any]:
        """Build a standardized report for a job based on its task type"""
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            raise ValueError(f"Job {trace_id} not found")

        if context.current_stage != "completed":
            raise ValueError(f"Job {trace_id} is not completed yet (current stage: {context.current_stage})")

        if context.task_type == "MORNING_REPORT":
            return await self.build_morning_report(trace_id, context)
        elif context.task_type == "SUMMARY_REPORT":
            return await self.build_summary_report(trace_id, context)
        else:
            raise ValueError(f"Report generation not supported for task type: {context.task_type}")

    async def build_morning_report(
        self, trace_id: str, context: Optional[JobContext] = None
    ) -> MorningReportResponse:
        """Build a standardized morning report from artifacts"""
        if context is None:
            context = await self.orchestrator.get_job_status(trace_id)
            if not context:
                raise ValueError(f"Job {trace_id} not found")

        # Get discovery results if available
        discovery_data = None
        discovery_key = context.artifacts.get("search_results")
        if discovery_key:
            try:
                discovery_data = await self.storage.get(discovery_key)
            except Exception as e:
                logger.warning(f"Failed to get discovery data from {discovery_key}: {e}")

        # Get init payload for input info
        init_key = context.init_key
        init_payload = None
        if init_key:
            try:
                init_payload = await self.storage.get(init_key)
            except Exception as e:
                logger.warning(f"Failed to get init payload from {init_key}: {e}")

        # Get manifest if available
        manifest = None
        manifest_key = context.artifacts.get("detailed_manifest")
        if manifest_key:
            try:
                manifest = await self.storage.get(manifest_key)
            except Exception as e:
                logger.warning(f"Failed to get manifest from {manifest_key}: {e}")

        papers = []
        completed_work_keys = context.completed_work_keys or []

        # Build papers from manifest if available, otherwise reconstruct from work_keys
        if manifest and isinstance(manifest, list):
            # Use manifest to get paper data
            for item in manifest:
                if not isinstance(item, dict):
                    continue

                work_key = item.get("work_key")
                if not work_key or work_key not in completed_work_keys:
                    continue

                paper_report = await self._build_paper_from_keys(
                    work_key, item.get("download_key"), item.get("parse_key"), item.get("index_key")
                )
                if paper_report:
                    papers.append(paper_report)
        else:
            # Fallback: reconstruct keys from work_keys (same logic as handlers)
            for work_key in completed_work_keys:
                if not work_key:
                    continue

                work_in_key = f"data:work:{work_key}"
                download_key = f"data:download:{work_in_key}"
                parse_key = f"data:parse:{download_key}"
                index_key = f"data:index:{parse_key}"

                paper_report = await self._build_paper_from_keys(work_key, download_key, parse_key, index_key)
                if paper_report:
                    papers.append(paper_report)

        # Convert failures to FailureInfo
        failure_infos = []
        for failure in context.failures:
            failure_infos.append(
                FailureInfo(
                    work_key=failure.work_key,
                    stage=failure.stage,
                    routing_key=failure.routing_key,
                    input_key=failure.input_key,
                    error_msg=failure.error_msg,
                )
            )

        # Extract input information
        input_info = {}
        if isinstance(init_payload, dict):
            input_info["query"] = init_payload.get("query")
            input_info["filters"] = init_payload.get("filters")
        elif discovery_data and isinstance(discovery_data, dict):
            # Fallback to discovery data
            input_info["query"] = discovery_data.get("query")
            input_info["filters"] = discovery_data.get("filters")

        # Build keys dict
        keys_dict = {
            "init_key": context.init_key,
            "discovery_key": context.artifacts.get("search_results"),
        }

        return MorningReportResponse(
            trace_id=context.trace_id,
            task_type=context.task_type,
            requested_limit=context.requested_limit,
            paper_count=len(papers),
            papers=papers,
            failure_count=len(failure_infos),
            failures=failure_infos,
            keys=keys_dict,
            input=input_info,
        )

    async def _build_paper_from_keys(
        self, work_key: str, download_key: Optional[str], parse_key: Optional[str], index_key: Optional[str]
    ) -> Optional[PaperReport]:
        """Build a PaperReport from storage keys"""
        try:
            # Get all payloads
            download_payload = None
            parse_payload = None
            index_payload = None

            if download_key:
                try:
                    download_payload = await self.storage.get(download_key)
                except Exception as e:
                    logger.warning(f"Failed to get download payload from {download_key}: {e}")

            if parse_key:
                try:
                    parse_payload = await self.storage.get(parse_key)
                except Exception as e:
                    logger.warning(f"Failed to get parse payload from {parse_key}: {e}")

            if index_key:
                try:
                    index_payload = await self.storage.get(index_key)
                except Exception as e:
                    logger.warning(f"Failed to get index payload from {index_key}: {e}")

            # Build paper metadata
            # Try to extract work info from download payload (if it contains work info)
            work_info = {}
            if isinstance(download_payload, dict):
                work_info = download_payload.get("work") or {}

            title = None
            if isinstance(parse_payload, dict):
                title = parse_payload.get("title")
            if not title and isinstance(download_payload, dict):
                title = download_payload.get("filename") or work_info.get("title")
            if not title:
                title = "Unknown"

            # Extract authors
            authors = []
            if isinstance(work_info, dict):
                authors = work_info.get("authors") or []
            if not authors and isinstance(parse_payload, dict):
                # Some parsers might include authors
                meta = parse_payload.get("meta") or {}
                if isinstance(meta, dict) and "authors" in meta:
                    authors = meta["authors"] if isinstance(meta["authors"], list) else []

            # Extract PDF URL and source
            pdf_url = None
            original_url = None
            if isinstance(download_payload, dict):
                pdf_url = download_payload.get("pdf_url")
                original_url = download_payload.get("source_url")
            if not original_url and isinstance(parse_payload, dict):
                meta = parse_payload.get("meta") or {}
                if isinstance(meta, dict):
                    original_url = meta.get("source_url")

            # Extract summary
            llm_summary = ""
            if isinstance(parse_payload, dict):
                llm_summary = parse_payload.get("llm_summary") or ""

            # Extract index info
            collection = None
            vector_count = None
            persist_dir = None
            if isinstance(index_payload, dict):
                collection = index_payload.get("collection")
                vector_count = index_payload.get("vector_count")
                persist_dir = index_payload.get("persist_dir")

            # Extract IDs from work_info
            openalex_id = None
            doi = None
            publication_date = None
            if isinstance(work_info, dict):
                openalex_id = work_info.get("openalex_id") or work_info.get("id")
                doi = work_info.get("doi")
                publication_date = work_info.get("publication_date")

            return PaperReport(
                paper=PaperMetadata(
                    title=title,
                    authors=authors,
                    pdf_url=pdf_url,
                    openalex_id=openalex_id,
                    doi=doi,
                    publication_date=publication_date,
                    original_url=original_url,
                ),
                summary=PaperSummary(llm_summary=llm_summary),
                index=IndexInfo(collection=collection, vector_count=vector_count, persist_dir=persist_dir),
                keys=PaperKeys(work_key=work_key, download_key=download_key, parse_key=parse_key, index_key=index_key),
            )

        except Exception as e:
            logger.error(f"Error building paper report for work_key {work_key}: {e}", exc_info=True)
            return None

    async def build_summary_report(
        self, trace_id: str, context: Optional[JobContext] = None
    ) -> SummaryReportResponse:
        """Build a standardized summary report from artifacts"""
        if context is None:
            context = await self.orchestrator.get_job_status(trace_id)
            if not context:
                raise ValueError(f"Job {trace_id} not found")

        # Summary report typically has an overview artifact
        # Try to find overview output key from artifacts
        overview_key = None
        for key, value in context.artifacts.items():
            if "overview" in key.lower() or (isinstance(value, str) and value.startswith("data:overview:")):
                overview_key = value
                break

        # If not found in artifacts, try common patterns
        if not overview_key:
            # Pattern 1: data:overview:task:{trace_id}:overview_in
            possible_keys = [
                f"data:overview:task:{trace_id}:overview_in",
            ]
            
            for key in possible_keys:
                try:
                    if await self.storage.exists(key):
                        overview_key = key
                        break
                except Exception:
                    continue

        overview_data = None
        if overview_key:
            try:
                overview_data = await self.storage.get(overview_key)
            except Exception as e:
                logger.warning(f"Failed to get overview data from {overview_key}: {e}")

        # Extract overview content
        overview_md = None
        meta = {}
        paper_count = None

        if isinstance(overview_data, dict):
            overview_md = overview_data.get("overview_md")
            meta = overview_data.get("meta") or {}
            paper_count = meta.get("paper_count")

        return SummaryReportResponse(
            trace_id=context.trace_id,
            task_type=context.task_type,
            overview_md=overview_md,
            meta=meta,
            paper_count=paper_count,
        )

