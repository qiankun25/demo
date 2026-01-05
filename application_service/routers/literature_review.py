from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import requests
import urllib.parse
import json
import asyncio
import time
from config import settings

router = APIRouter(prefix="/api/literature-review", tags=["Literature Review"])

# Configuration
API_BASE_URL = settings.API_BASE_URL
BASE_HOST = settings.BASE_HOST
POLL_INTERVAL = 3  # seconds
MAX_WAIT = 600  # 最大等待时间：10分钟


class PaperItem(BaseModel):
    """论文项"""
    pdf_url: str
    title: str = ""  # 标题，默认为空字符串
    authors: List[str] = Field(default_factory=list)  # 作者列表，默认为空列表


class LiteratureReviewRequest(BaseModel):
    """Literature Review 请求参数"""
    papers: List[PaperItem]  # 论文列表
    domain: Optional[str] = None  # 可选：领域，如 "machine_learning", "medical"
    style: Optional[str] = None  # 可选：风格，如 "academic", "concise"


class LiteratureReviewResponse(BaseModel):
    """Literature Review 响应 - 包含最终报告"""
    trace_id: str
    final_report: Optional[Dict[str, Any]] = None


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
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        return response.json()


# 注意：文件上传已改为直接上传到 MinIO 服务器（地址从环境变量 MINIO_UPLOAD_URL 读取）
# 前端会将文件上传到 MinIO 获取 presigned URL，然后将 URL 发送给后端
# 因此不再需要此处的 /upload 端点
# 如需文件上传功能，请使用 MinIO 服务器的 /upload 端点

@router.post("", response_model=LiteratureReviewResponse)
async def create_literature_review(request: LiteratureReviewRequest):
    """
    创建并执行 Literature Review 任务（综述生成）
    
    基于 test_nexus_api.py 中的 test_summary_report() 方法实现
    
    这个接口会：
    1. 提交 SUMMARY_REPORT 任务到外部 API
    2. 等待任务完成
    3. 获取标准化报告（使用 /jobs/{trace_id}/report 端点）
    
    请求参数：
    - papers: 论文列表，每个论文包含 pdf_url, title, authors
    - domain: 可选，领域，如 "machine_learning", "medical"
    - style: 可选，风格，如 "academic", "concise"
    """
    client = NexusAPIClient()
    
    # 1. 准备参数
    # 将 PaperItem 模型转换为字典格式
    papers_data = [paper.model_dump() for paper in request.papers]
    
    parameters = {
        "papers": papers_data
    }
    
    # 添加可选参数
    if request.domain:
        parameters["domain"] = request.domain
    if request.style:
        parameters["style"] = request.style
    
    # 2. 提交任务
    def _submit():
        return client.submit_job("SUMMARY_REPORT", parameters)
    
    try:
        trace_id = await asyncio.to_thread(_submit)
    except Exception as e:
        error_msg = f"提交任务失败: {e}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
    
    # 3. 等待任务完成
    def _wait():
        return client.wait_for_completion(trace_id, poll_interval=POLL_INTERVAL, max_wait=MAX_WAIT)
    
    try:
        final_status = await asyncio.to_thread(_wait)
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"任务执行失败: {e}"
        )
    
    # 4. 获取最终报告（使用标准化报告端点）
    def _get_final_report():
        try:
            return client.get_report(trace_id)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_detail = e.response.json().get('detail', '')
                raise Exception(f"任务尚未完成: {error_detail}")
            else:
                raise Exception(f"获取报告失败: HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise Exception(f"获取报告失败: {e}")
    
    try:
        final_report = await asyncio.to_thread(_get_final_report)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
    # 5. 返回结果
    return LiteratureReviewResponse(
        trace_id=trace_id,
        final_report=final_report
    )

