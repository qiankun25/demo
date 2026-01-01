"""Service for building standardized reports from job artifacts"""

import logging
from typing import Dict, Any, Optional, List
import httpx
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

        # Get discovery results if available (prefer claim-check ref + query API)
        discovery_data = None
        discovery_ref = (getattr(context, "artifacts_refs", {}) or {}).get("search_results")
        if isinstance(discovery_ref, dict) and discovery_ref.get("type") == "search_result" and discovery_ref.get("id"):
            try:
                url = self.orchestrator.settings.discovery_base_url.rstrip("/") + f"/v1/results/{discovery_ref['id']}"
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    r = await client.get(url)
                    r.raise_for_status()
                    data = r.json()
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    discovery_data = data["data"]
            except Exception as e:
                logger.warning(f"Failed to get discovery data via ref {discovery_ref}: {e}")
        papers = []
        completed_work_keys = context.completed_work_keys or []
        for work_key in completed_work_keys:
            pr = await self._build_paper_ref_only(context, work_key)
            if pr:
                papers.append(pr)

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

        input_info = {}
        if isinstance(context.metadata, dict):
            input_info["query"] = context.metadata.get("query")
            input_info["filters"] = context.metadata.get("filters")
        elif discovery_data and isinstance(discovery_data, dict):
            input_info["query"] = discovery_data.get("query")
            input_info["filters"] = discovery_data.get("filters")

        # Build keys dict
        keys_dict = {"init_key": None, "discovery_key": None}

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

    async def _build_paper_ref_only(self, context: JobContext, work_key: str) -> Optional[PaperReport]:
        """Build a PaperReport using refs + Query APIs (no shared storage keys)."""
        try:
            paper_meta = {}
            if isinstance(context.metadata, dict):
                wm = context.metadata.get("work_meta") or {}
                if isinstance(wm, dict):
                    paper_meta = wm.get(work_key) or {}
            if not isinstance(paper_meta, dict):
                paper_meta = {}

            title = str(paper_meta.get("title") or "Unknown")
            authors = paper_meta.get("authors") or []
            if not isinstance(authors, list):
                authors = []
            pdf_url = paper_meta.get("pdf_url")

            refs = getattr(context, "artifacts_refs", {}) or {}
            parse_ref = refs.get(f"parser:{work_key}") if isinstance(refs, dict) else None

            llm_summary = ""
            if isinstance(parse_ref, dict) and parse_ref.get("type") == "parsed_doc" and parse_ref.get("id"):
                pbase = self.orchestrator.settings.parser_base_url.rstrip("/")
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    r = await client.get(f"{pbase}/v1/parsed/{parse_ref['id']}")
                    if r.status_code < 400:
                        pdata = r.json()
                        doc = pdata.get("data") if isinstance(pdata, dict) else None
                        if isinstance(doc, dict):
                            chunks = doc.get("chunks") or []
                            if isinstance(chunks, list) and chunks:
                                c0 = chunks[0] if isinstance(chunks[0], dict) else {}
                                llm_summary = str(c0.get("text") or "")[:800]

            return PaperReport(
                paper=PaperMetadata(
                    title=title,
                    authors=[str(a) for a in authors],
                    pdf_url=pdf_url,
                    openalex_id=paper_meta.get("canonical_id") or paper_meta.get("openalex_id"),
                    doi=paper_meta.get("doi"),
                    publication_date=paper_meta.get("publication_date"),
                    original_url=pdf_url,
                ),
                summary=PaperSummary(llm_summary=llm_summary),
                index=IndexInfo(),
                keys=PaperKeys(work_key=work_key, download_key=None, parse_key=None, index_key=None),
            )
        except Exception as e:
            logger.warning(f"Failed to build paper (ref-only) for {work_key}: {e}")
            return None

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

        # Ref-only: overview is fetched via overview-service Query API using result_ref
        overview_data = None
        refs = getattr(context, "artifacts_refs", {}) or {}
        overview_ref = refs.get("overview") if isinstance(refs, dict) else None
        if isinstance(overview_ref, dict) and overview_ref.get("type") == "overview_report" and overview_ref.get("id"):
            try:
                base = self.orchestrator.settings.overview_base_url.rstrip("/")
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    r = await client.get(f"{base}/v1/reports/{overview_ref['id']}")
                    r.raise_for_status()
                    overview_data = r.json()
            except Exception as e:
                logger.warning(f"Failed to get overview via API: {e}")

        # Extract overview content
        overview_md = None
        meta = {}
        paper_count = None

        if isinstance(overview_data, dict):
            data = overview_data.get("data") if isinstance(overview_data.get("data"), dict) else overview_data
            overview_md = data.get("overview_md")
            meta = data.get("meta") or {}
            paper_count = (meta.get("paper_count") if isinstance(meta, dict) else None)

        return SummaryReportResponse(
            trace_id=context.trace_id,
            task_type=context.task_type,
            overview_md=overview_md,
            meta=meta,
            paper_count=paper_count,
        )

