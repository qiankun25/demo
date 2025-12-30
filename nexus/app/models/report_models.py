"""Report response models for standardized report API"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class PaperMetadata(BaseModel):
    """Paper metadata information"""
    title: str
    authors: List[str] = Field(default_factory=list)
    pdf_url: Optional[str] = None
    openalex_id: Optional[str] = None
    doi: Optional[str] = None
    publication_date: Optional[str] = None
    original_url: Optional[str] = None


class PaperSummary(BaseModel):
    """Paper summary information"""
    llm_summary: str = ""


class IndexInfo(BaseModel):
    """Index information"""
    collection: Optional[str] = None
    vector_count: Optional[int] = None
    persist_dir: Optional[str] = None


class PaperKeys(BaseModel):
    """Paper-related storage keys"""
    work_key: str
    download_key: Optional[str] = None
    parse_key: Optional[str] = None
    index_key: Optional[str] = None


class PaperReport(BaseModel):
    """Report for a single paper"""
    paper: PaperMetadata
    summary: PaperSummary
    index: IndexInfo
    keys: PaperKeys


class FailureInfo(BaseModel):
    """Failure information"""
    work_key: str
    stage: str
    routing_key: str
    input_key: str
    error_msg: str


class MorningReportResponse(BaseModel):
    """Standardized morning report response"""
    trace_id: str
    task_type: str = "MORNING_REPORT"
    requested_limit: int
    paper_count: int
    papers: List[PaperReport] = Field(default_factory=list)
    failure_count: int = 0
    failures: List[FailureInfo] = Field(default_factory=list)
    keys: Dict[str, Optional[str]] = Field(default_factory=dict)
    input: Dict[str, Any] = Field(default_factory=dict)


class SummaryReportResponse(BaseModel):
    """Standardized summary report response"""
    trace_id: str
    task_type: str = "SUMMARY_REPORT"
    overview_md: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    paper_count: Optional[int] = None


class ReportResponse(BaseModel):
    """Generic report response (union type)"""
    trace_id: str
    task_type: str
    data: Dict[str, Any]  # Task-specific report data


