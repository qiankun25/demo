from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union, List
import requests
import urllib.parse
import json
import asyncio
import time
from config import settings

router = APIRouter(prefix="/api/morning-report", tags=["Morning Report"])

# Configuration
API_BASE_URL = settings.API_BASE_URL
BASE_HOST = settings.BASE_HOST
POLL_INTERVAL = 3  # seconds
MAX_WAIT = 600  # 最大等待时间：10分钟


class MorningReportRequest(BaseModel):
    """Morning Report 请求参数"""
    query: str = "Large Language Models"
    limit: int = 5
    filters: Optional[Dict[str, Any]] = None


class MorningReportSubmitResponse(BaseModel):
    """Morning Report 提交任务响应"""
    trace_id: str
    status: str
    message: str


class MorningReportResponse(BaseModel):
    """Morning Report 获取结果响应"""
    trace_id: str
    search_results: Dict[str, Any]


class NexusAPIClient:
    """Nexus API 客户端 - 从 api_usage_examples.py 移植"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.BASE_HOST
        self.api_prefix = settings.API_BASE_URL
        self.session = requests.Session()
        self.session.timeout = 30
    
    def _unwrap_claimcheck(self, raw: bytes) -> Any:
        """解包 Nexus Claim-Check 格式的数据"""
        MAGIC = b"NEXUS_CLAIMCHECK_V1\n"
        if not raw.startswith(MAGIC):
            return raw
        
        rest = raw[len(MAGIC):]
        sep = rest.find(b"\n\n")
        if sep < 0:
            return rest
        
        meta = rest[:sep].decode("utf-8", errors="replace")
        body = rest[sep + 2:]
        encoding = "raw"
        
        for line in meta.splitlines():
            if line.startswith("encoding:"):
                encoding = line.split(":", 1)[1].strip()
                break
        
        if encoding == "json":
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return body
        elif encoding == "pickle":
            try:
                import pickle
                return pickle.loads(body)
            except Exception:
                return body
        
        return body
    
    def _get_artifact_data(self, trace_id: str, artifact_key: str) -> Any:
        """获取 Artifact 数据（支持逻辑键和 storage_key）"""
        # URL 编码 storage_key
        if artifact_key.startswith("data:"):
            encoded_key = urllib.parse.quote(artifact_key, safe='')
        else:
            encoded_key = artifact_key
        
        url = f"{self.api_prefix}/jobs/{trace_id}/artifacts/{encoded_key}"
        response = self.session.get(url, timeout=120)
        response.raise_for_status()
        
        # 获取原始字节数据
        raw_data = response.content
        
        # 首先尝试解包 Claim-Check 格式
        unwrapped = self._unwrap_claimcheck(raw_data)
        
        # 如果解包后不是原始 bytes，说明已经解析成功
        if unwrapped is not raw_data and not isinstance(unwrapped, bytes):
            return unwrapped
        
        # 如果解包后仍然是 bytes，继续尝试其他解析方式
        data = unwrapped
        
        # 检查 content-type
        content_type = response.headers.get('Content-Type', '').lower()
        
        # 尝试解析为 JSON（如果 content-type 是 json，或者内容看起来像 JSON）
        if 'json' in content_type:
            try:
                return response.json()
            except json.JSONDecodeError:
                pass
        
        # 尝试解析内容（可能是 JSON 但没有正确的 content-type）
        if isinstance(data, bytes):
            try:
                text = data.decode('utf-8')
                if text.strip().startswith('{') or text.strip().startswith('['):
                    return json.loads(text)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        # 返回原始内容（可能是二进制数据）
        return data
    
    def submit_job(self, task_type: str, parameters: Dict[str, Any]) -> str:
        """提交任务"""
        url = f"{self.api_prefix}/jobs"
        response = self.session.post(url, json={
            "task_type": task_type,
            "parameters": parameters
        })
        response.raise_for_status()
        return response.json()["trace_id"]
    
    def get_job_status(self, trace_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        url = f"{self.api_prefix}/jobs/{trace_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, trace_id: str, poll_interval: int = 3, max_wait: int = 600) -> Dict[str, Any]:
        """等待任务完成"""
        start_time = time.time()
        while True:
            if time.time() - start_time > max_wait:
                raise TimeoutError(f"任务超时（超过 {max_wait} 秒）")
            
            status = self.get_job_status(trace_id)
            current_status = status.get("status", "unknown")
            
            if current_status == "completed":
                return status
            elif current_status == "failed":
                raise Exception(f"任务失败: {status.get('failures', [])}")
            
            time.sleep(poll_interval)
    
    def get_report(self, trace_id: str) -> Dict[str, Any]:
        """获取标准化报告"""
        url = f"{self.api_prefix}/jobs/{trace_id}/report"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


def convert_report_to_search_results(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 API 返回的标准化报告格式转换为前端期望的 search_results 格式
    
    根据 API_REFERENCE.md，MORNING_REPORT 的响应格式是：
    {
      "trace_id": "uuid",
      "task_type": "MORNING_REPORT",
      "papers": [
        {
          "paper": {...},
          "summary": {
            "llm_summary": "..."
          },
          ...
        }
      ],
      ...
    }
    
    需要转换为：
    {
      "results": [
        {
          ...paper对象的所有字段...,
          "llm_summary": "..."
        }
      ]
    }
    """
    if not isinstance(report_data, dict):
        return {"results": []}
    
    papers = report_data.get("papers", [])
    
    # 转换每个 paper 对象
    results = []
    for paper_item in papers:
        if not isinstance(paper_item, dict):
            continue
        
        # 提取 paper 对象
        paper = paper_item.get("paper", {})
        if not isinstance(paper, dict):
            continue
        
        # 提取 summary
        summary = paper_item.get("summary", {})
        llm_summary = summary.get("llm_summary") if isinstance(summary, dict) else None
        
        # 合并 paper 对象和 llm_summary
        result_item = paper.copy()
        if llm_summary:
            result_item["llm_summary"] = llm_summary
        
        # 移除 locations 字段（如果存在）
        if "locations" in result_item:
            del result_item["locations"]
        
        results.append(result_item)
    
    return {"results": results}


@router.post("", response_model=MorningReportSubmitResponse)
async def create_morning_report(request: MorningReportRequest):
    """
    提交 Morning Report 任务
    
    提交任务到外部API，返回trace_id，前端需要轮询获取结果
    """
    client = NexusAPIClient()
    
    # 提交任务
    def _submit():
        return client.submit_job(
            "MORNING_REPORT",
            {
                "query": request.query,
                "limit": request.limit,
                "filters": request.filters or {"last_n_days": 30}
            }
        )
    
    try:
        trace_id = await asyncio.to_thread(_submit)
        return MorningReportSubmitResponse(
            trace_id=trace_id,
            status="submitted",
            message="Job submitted successfully"
        )
    except Exception as e:
        error_msg = f"提交任务失败: {e}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/{trace_id}", response_model=MorningReportResponse)
async def get_morning_report(trace_id: str):
    """
    获取 Morning Report 结果
    
    通过trace_id从外部API获取报告数据
    根据 API_REFERENCE.md，API 返回的是标准化报告格式，包含 papers 数组
    需要转换为前端期望的 search_results 格式
    """
    client = NexusAPIClient()
    
    def _get_report():
        return client.get_report(trace_id)
    
    try:
        report_data = await asyncio.to_thread(_get_report)
        
        # 根据 API_REFERENCE.md，返回格式是 {trace_id, task_type, papers, ...}
        # 需要转换为前端期望的 {search_results: {results: [...]}} 格式
        search_results = convert_report_to_search_results(report_data)
        
        if not search_results.get("results"):
            # 检查是否有 papers 数据
            if report_data.get("papers"):
                # 有 papers 但转换失败，可能是格式问题
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="报告数据格式转换失败"
                )
            else:
                # 没有 papers 数据，返回空结果
                search_results = {"results": []}
        
        return MorningReportResponse(
            trace_id=trace_id,
            search_results=search_results
        )
    except HTTPException:
        raise
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            # 根据 API_REFERENCE.md，400 表示任务尚未完成
            error_detail = e.response.json().get("detail", "任务尚未完成，请稍后再试")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail
            )
        elif e.response.status_code == 404:
            # 404 表示任务未找到
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务 {trace_id} 未找到"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取报告失败: {e.response.text if hasattr(e, 'response') else str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取报告失败: {str(e)}"
        )


# 注意：根据 API_REFERENCE.md，外部API (/api/v1/jobs/{trace_id}/report) 返回的是标准化报告格式
# MORNING_REPORT 类型返回 {trace_id, task_type, papers, ...} 格式
# 需要使用 convert_report_to_search_results 转换为前端期望的格式

