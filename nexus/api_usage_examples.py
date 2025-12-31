"""
Nexus API 使用示例代码
包含学术早报和综述生成两个功能的完整示例
"""

import requests
import urllib.parse
import json
import time
from typing import Dict, List, Any, Optional


class NexusAPIClient:
    """Nexus API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = f"{base_url}/api/v1"
        self.session = requests.Session()
        self.session.timeout = 30
    
    def _unwrap_claimcheck(self, raw: bytes) -> Any:
        """解包 Nexus Claim-Check 格式的数据
        
        Claim-Check 格式：
        NEXUS_CLAIMCHECK_V1\n
        encoding:json\n
        \n
        {实际数据}
        """
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
            
            print(f"  状态: {current_status}, "
                  f"完成: {status.get('completed_count', 0)}/{status.get('total_work_items', 0)}")
            
            if current_status == "completed":
                return status
            elif current_status == "failed":
                raise Exception(f"任务失败: {status.get('failures', [])}")
            
            time.sleep(poll_interval)


# ============================================================================
# 功能 1: 学术早报 (MORNING_REPORT)
# ============================================================================

def morning_report_example():
    """
    学术早报功能示例
    
    需要获取的数据：
    1. 搜索结果 (search_results) - JSON 格式
    2. Parse 结果 - 每个工作项的解析数据，JSON 格式
    """
    print("=" * 80)
    print("学术早报 (MORNING_REPORT) 示例")
    print("=" * 80)
    
    client = NexusAPIClient()
    
    # 1. 提交任务
    print("\n[1] 提交任务...")
    trace_id = client.submit_job(
        "MORNING_REPORT",
        {
            "query": "Large Language Models",
            "limit": 5,
            "filters": {
                "last_n_days": 30
            }
        }
    )
    print(f"Trace ID: {trace_id}")
    
    # 2. 等待完成
    print("\n[2] 等待任务完成...")
    final_status = client.wait_for_completion(trace_id)
    
    # 3. 获取搜索结果
    print("\n[3] 获取搜索结果...")
    artifacts = final_status.get("artifacts", {})
    search_results_key = artifacts.get("search_results")
    
    if not search_results_key:
        raise ValueError("搜索结果不存在")
    
    # search_results_key 是相对路径，需要拼接
    if search_results_key.startswith("/"):
        search_results_url = f"{client.base_url}{search_results_key}"
    else:
        search_results_url = search_results_key
    
    search_results = client._get_artifact_data(trace_id, search_results_key.split("/")[-1])
    
    print("\n" + "=" * 20 + " 搜索结果 (Search Results) " + "=" * 20)
    print(json.dumps(search_results, indent=2, ensure_ascii=False))
    
    # 4. 获取 Manifest
    print("\n[4] 获取 Manifest...")
    manifest_key = artifacts.get("detailed_manifest")
    if not manifest_key:
        # 尝试 fallback
        manifest_key = f"data:manifest:{trace_id}"
    
    if manifest_key.startswith("/"):
        manifest_url = f"{client.base_url}{manifest_key}"
        manifest = requests.get(manifest_url).json()
    else:
        manifest = client._get_artifact_data(trace_id, manifest_key.split("/")[-1] if "/" in manifest_key else manifest_key)
    
    print(f"✓ Manifest 获取成功，包含 {len(manifest)} 个工作项")
    
    # 5. 获取所有工作项的 Parse 结果
    print("\n[5] 获取所有工作项的 Parse 结果...")
    parse_results = []
    
    for idx, item in enumerate(manifest):
        work_key = item.get("work_key")
        parse_key = item.get("parse_key")
        
        if not parse_key:
            continue
        
        print(f"\n--- 工作项 {idx} ({work_key}) ---")
        parse_data = client._get_artifact_data(trace_id, parse_key)
        print(json.dumps(parse_data, indent=2, ensure_ascii=False))
        
        parse_results.append({
            "work_key": work_key,
            "parse_data": parse_data
        })
    
    # 6. 返回结果
    return {
        "trace_id": trace_id,
        "search_results": search_results,
        "parse_results": parse_results
    }


# ============================================================================
# 功能 2: 综述生成 (SUMMARY_REPORT)
# ============================================================================

def summary_report_example():
    """
    综述生成功能示例
    
    需要获取的数据：
    1. 最终报告 (Overview 服务的输出) - JSON 格式
    
    注意：SUMMARY_REPORT 需要先有一个 summary_report_key，包含要处理的论文列表
    """
    print("=" * 80)
    print("综述生成 (SUMMARY_REPORT) 示例")
    print("=" * 80)
    
    client = NexusAPIClient()
    
    # 1. 准备输入数据（论文列表）
    # 注意：实际使用中，这个 summary_report_key 应该已经存在于存储中
    # 这里假设已经有一个包含论文列表的 storage_key
    print("\n[1] 准备输入数据...")
    print("注意：SUMMARY_REPORT 需要 summary_report_key 参数")
    print("该 key 指向一个包含 papers 列表的数据，格式如下：")
    print("""
    {
        "papers": [
            {
                "title": "论文标题",
                "authors": ["作者1"],
                "pdf_url": "PDF URL"
            }
        ]
    }
    """)
    
    # 示例：假设已经有一个 summary_report_key
    # 实际使用时，这个 key 应该从之前的任务或数据准备步骤中获得
    summary_report_key = "data:summary_report:example_key"  # 替换为实际的 key
    
    # 2. 提交任务
    print("\n[2] 提交任务...")
    trace_id = client.submit_job(
        "SUMMARY_REPORT",
        {
            "summary_report_key": summary_report_key,
            "domain": "medical",  # 可选：领域
            "style": "academic"   # 可选：风格
        }
    )
    print(f"Trace ID: {trace_id}")
    
    # 3. 等待完成
    print("\n[3] 等待任务完成...")
    final_status = client.wait_for_completion(trace_id)
    
    # 4. 获取最终报告
    print("\n[4] 获取最终报告...")
    
    # SUMMARY_REPORT 的最终输出在 Overview 服务完成后
    # 根据 Overview 服务的实现，output_key 格式为: data:overview:{input_key}
    # 其中 input_key 是: task:{trace_id}:overview_in
    # 所以 output_key = data:overview:task:{trace_id}:overview_in
    
    overview_output_key = f"data:overview:task:{trace_id}:overview_in"
    
    try:
        final_report = client._get_artifact_data(trace_id, overview_output_key)
    except Exception as e:
        print(f"⚠️  警告：无法获取最终报告: {e}")
        print(f"   尝试的 storage_key: {overview_output_key}")
        return {
            "trace_id": trace_id,
            "status": "completed",
            "report": None,
            "error": str(e)
        }
    
    """
    最终报告 JSON 字段说明（根据 Overview 服务的实际输出）：
    {
        "overview_md": "生成的综述内容（Markdown 格式）",
        "meta": {
            "model": "使用的模型名称",
            "paper_count": 处理的论文数量,
            "domain": "领域（如果有）",
            "style": "风格（如果有，如 academic/concise）"
        }
    }
    """
    print(f"✓ 最终报告获取成功")
    
    # 5. 返回结果
    return {
        "trace_id": trace_id,
        "final_report": final_report
    }


# ============================================================================
# 主函数
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "morning":
            result = morning_report_example()
            print("\n" + "=" * 80)
            print("结果摘要:")
            print(f"Trace ID: {result['trace_id']}")
            print(f"搜索结果数量: {len(result['search_results'].get('results', []))}")
            print(f"Parse 结果数量: {len(result['parse_results'])}")
        elif sys.argv[1] == "summary":
            result = summary_report_example()
            print("\n" + "=" * 80)
            print("结果摘要:")
            print(f"Trace ID: {result['trace_id']}")
            if result.get('final_report'):
                print("最终报告已获取")
            else:
                print("最终报告未找到")
        else:
            print("用法: python api_usage_examples.py [morning|summary]")
    else:
        print("请指定功能:")
        print("  python api_usage_examples.py morning  # 学术早报")
        print("  python api_usage_examples.py summary  # 综述生成")

