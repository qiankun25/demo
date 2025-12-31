"""
Nexus API 客户端测试程序
用于测试与 Nexus 服务的完整交互流程
"""

import requests
import urllib.parse
import time
import json
from typing import List, Dict, Any, Optional


class NexusClient:
    """Nexus API 客户端封装"""
    
    def __init__(self, base_url: str = "http://8.134.183.68:8000"):
        self.base_url = base_url
        self.api_prefix = f"{base_url}/api/v1"
        self.session = requests.Session()
        # 设置超时
        self.session.timeout = 30
    
    def submit_job(self, task_type: str, parameters: dict) -> str:
        """提交任务，返回 trace_id"""
        url = f"{self.api_prefix}/jobs"
        print(f"[提交任务] POST {url}")
        print(f"  任务类型: {task_type}")
        print(f"  参数: {json.dumps(parameters, indent=2, ensure_ascii=False)}")
        
        try:
            response = self.session.post(
                url,
                json={"task_type": task_type, "parameters": parameters}
            )
            response.raise_for_status()
            result = response.json()
            trace_id = result["trace_id"]
            print(f"[提交成功] trace_id: {trace_id}")
            return trace_id
        except requests.exceptions.RequestException as e:
            print(f"[提交失败] 错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  响应状态码: {e.response.status_code}")
                print(f"  响应内容: {e.response.text}")
            raise
    
    def get_job_status(self, trace_id: str) -> dict:
        """获取任务状态"""
        url = f"{self.api_prefix}/jobs/{trace_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[获取状态失败] trace_id={trace_id}, 错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  响应状态码: {e.response.status_code}")
                print(f"  响应内容: {e.response.text}")
            raise
    
    def wait_for_completion(self, trace_id: str, poll_interval: int = 2, max_wait: int = 300) -> dict:
        """等待任务完成（轮询）"""
        print(f"\n[等待完成] trace_id: {trace_id}")
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise TimeoutError(f"任务超时（等待超过 {max_wait} 秒）")
            
            try:
                status = self.get_job_status(trace_id)
                current_status = status.get("status", "unknown")
                completed = status.get("completed_count", 0)
                total = status.get("total_work_items", 0)
                failed = status.get("failed_count", 0)
                
                print(f"  [{elapsed:.0f}s] 状态: {current_status}, "
                      f"完成: {completed}/{total}, 失败: {failed}")
                
                if current_status == "completed":
                    print(f"[任务完成] 总耗时: {elapsed:.1f} 秒")
                    return status
                elif current_status == "failed":
                    print(f"[任务失败]")
                    return status
                
                time.sleep(poll_interval)
            except requests.exceptions.RequestException as e:
                print(f"  轮询错误: {e}，继续重试...")
                time.sleep(poll_interval)
    
    def get_artifact(self, trace_id: str, artifact_key: str, stream: bool = False):
        """获取 Artifact（支持逻辑键或 storage_key）"""
        # URL 编码（如果是 storage_key，需要编码特殊字符）
        if artifact_key.startswith("data:"):
            # 对 storage_key 进行 URL 编码
            encoded_key = urllib.parse.quote(artifact_key, safe='')
        else:
            encoded_key = artifact_key
        
        url = f"{self.api_prefix}/jobs/{trace_id}/artifacts/{encoded_key}"
        
        try:
            response = self.session.get(url, stream=stream)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[获取 Artifact 失败] trace_id={trace_id}, key={artifact_key}")
            print(f"  编码后的 key: {encoded_key}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  响应状态码: {e.response.status_code}")
                print(f"  响应内容: {e.response.text[:500]}")
            raise
    
    def get_manifest(self, trace_id: str) -> Optional[List[Dict[str, str]]]:
        """获取 Manifest 清单
        
        Returns:
            Manifest 列表，如果不存在则返回 None
        """
        status = self.get_job_status(trace_id)
        
        # 使用逻辑键获取 Manifest
        artifacts = status.get("artifacts", {})
        manifest_url = artifacts.get("detailed_manifest")
        
        # 如果 artifacts 中没有 detailed_manifest，尝试使用 fallback storage_key
        if not manifest_url:
            # 尝试直接使用 storage_key 获取
            fallback_key = f"data:manifest:{trace_id}"
            print(f"[获取 Manifest] artifacts 中未找到 detailed_manifest，尝试使用 storage_key: {fallback_key}")
            try:
                response = self.get_artifact(trace_id, fallback_key)
                manifest = response.json()
                print(f"[Manifest 获取成功] 包含 {len(manifest)} 个工作项")
                return manifest
            except Exception as e:
                # 检查是否是因为没有工作项
                total_items = status.get("total_work_items", 0)
                if total_items == 0:
                    print(f"[提示] 任务已完成，但未找到任何工作项（Discovery 阶段可能没有找到有效的 PDF 候选）")
                    print(f"  这通常意味着搜索查询没有返回可用的论文，或者所有结果都没有 PDF 链接")
                    return None
                else:
                    print(f"[获取 Manifest 失败] 错误: {e}")
                    raise ValueError(f"Manifest not found. Status: {json.dumps(status, indent=2, ensure_ascii=False)}")
        
        # manifest_url 是相对路径（如 "/api/v1/jobs/xxx/artifacts/yyy"），需要拼接 base_url
        if manifest_url.startswith("/"):
            manifest_url = f"{self.base_url}{manifest_url}"
        elif not manifest_url.startswith("http"):
            manifest_url = f"{self.base_url}/{manifest_url}"
        
        print(f"[获取 Manifest] URL: {manifest_url}")
        try:
            response = self.session.get(manifest_url)
            response.raise_for_status()
            manifest = response.json()
            print(f"[Manifest 获取成功] 包含 {len(manifest)} 个工作项")
            return manifest
        except requests.exceptions.RequestException as e:
            print(f"[获取 Manifest 失败] 错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  响应状态码: {e.response.status_code}")
                print(f"  响应内容: {e.response.text[:500]}")
            raise
    
    def get_parse_data(self, trace_id: str, parse_key: str) -> dict:
        """获取解析后的数据"""
        response = self.get_artifact(trace_id, parse_key)
        return response.json()
    
    def get_all_parse_data(self, trace_id: str) -> List[dict]:
        """获取所有工作项的解析数据"""
        manifest = self.get_manifest(trace_id)
        
        if manifest is None:
            print("[获取所有解析数据] Manifest 不存在，无法获取数据")
            return []
        
        results = []
        
        print(f"\n[获取所有解析数据] 开始处理 {len(manifest)} 个工作项")
        
        for idx, item in enumerate(manifest, 1):
            work_key = item.get("work_key", "unknown")
            parse_key = item.get("parse_key")
            
            if not parse_key:
                print(f"  [{idx}/{len(manifest)}] {work_key}: 缺少 parse_key")
                results.append({
                    "work_key": work_key,
                    "error": "parse_key not found in manifest item"
                })
                continue
            
            try:
                print(f"  [{idx}/{len(manifest)}] 获取 {work_key} 的数据...")
                parse_data = self.get_parse_data(trace_id, parse_key)
                results.append({
                    "work_key": work_key,
                    "data": parse_data
                })
                print(f"    ✓ 成功")
            except Exception as e:
                print(f"    ✗ 失败: {e}")
                results.append({
                    "work_key": work_key,
                    "parse_key": parse_key,
                    "error": str(e)
                })
        
        return results
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            # 健康检查端点在 API 路由下
            url = f"{self.api_prefix}/health"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            result = response.json()
            print(f"[健康检查] {result}")
            return result.get("status") == "healthy"
        except Exception as e:
            print(f"[健康检查失败] 错误: {e}")
            return False


def test_full_workflow():
    """完整工作流测试"""
    print("=" * 60)
    print("Nexus API 完整工作流测试")
    print("=" * 60)
    
    client = NexusClient()
    
    # 0. 健康检查
    print("\n[步骤 0] 健康检查")
    if not client.health_check():
        print("警告: 服务可能不健康，但继续测试...")
    
    try:
        # 1. 提交任务
        print("\n[步骤 1] 提交任务")
        trace_id = client.submit_job(
            "MORNING_REPORT",
            {"limit": 5, "query": "LLM Agents"}
        )
        
        # 2. 等待完成
        print("\n[步骤 2] 等待任务完成")
        final_status = client.wait_for_completion(trace_id, poll_interval=3)
        
        # 显示最终状态摘要
        print("\n[任务状态摘要]")
        print(f"  trace_id: {trace_id}")
        print(f"  状态: {final_status.get('status')}")
        print(f"  任务类型: {final_status.get('task_type')}")
        print(f"  总工作项: {final_status.get('total_work_items')}")
        print(f"  已完成: {final_status.get('completed_count')}")
        print(f"  失败: {final_status.get('failed_count')}")
        print(f"  待处理: {final_status.get('pending_count')}")
        
        artifacts = final_status.get("artifacts", {})
        if artifacts:
            print(f"  可用 Artifacts: {list(artifacts.keys())}")
        
        # 3. 获取 Manifest
        print("\n[步骤 3] 获取 Manifest")
        manifest = client.get_manifest(trace_id)
        
        if manifest is None:
            print("\n[提示] 任务已完成，但没有生成 Manifest（可能因为没有找到有效的工作项）")
            print("  建议：")
            print("    1. 检查搜索查询是否返回了结果")
            print("    2. 确认返回的结果中是否有可用的 PDF 链接")
            print("    3. 尝试使用不同的查询关键词")
            return
        
        if len(manifest) == 0:
            print("\n[提示] Manifest 为空，没有工作项")
            return
        
        print(f"\nManifest 内容预览（前 2 项）:")
        for item in manifest[:2]:
            print(json.dumps(item, indent=2, ensure_ascii=False))
        
        # 4. 获取所有解析数据
        print("\n[步骤 4] 获取所有解析数据")
        all_data = client.get_all_parse_data(trace_id)
        
        # 显示结果摘要
        print("\n[数据获取摘要]")
        success_count = sum(1 for item in all_data if "data" in item)
        error_count = sum(1 for item in all_data if "error" in item)
        print(f"  成功: {success_count}/{len(all_data)}")
        print(f"  失败: {error_count}/{len(all_data)}")
        
        # 显示每个工作项的关键信息
        print("\n[工作项详情]")
        for item in all_data:
            work_key = item.get("work_key", "unknown")
            if "data" in item:
                data = item["data"]
                title = data.get("title", "N/A")
                summary_preview = data.get("llm_summary", "")
                if summary_preview:
                    summary_preview = summary_preview[:100] + "..." if len(summary_preview) > 100 else summary_preview
                else:
                    summary_preview = "N/A"
                
                print(f"\n  {work_key}:")
                print(f"    标题: {title}")
                print(f"    摘要: {summary_preview}")
            else:
                error = item.get("error", "Unknown error")
                print(f"\n  {work_key}: [错误] {error}")
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[测试失败] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_quick_status_check(trace_id: str):
    """快速状态检查（用于已有任务）"""
    print(f"\n[快速状态检查] trace_id: {trace_id}")
    client = NexusClient()
    
    try:
        status = client.get_job_status(trace_id)
        print("\n状态信息:")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        
        if status.get("status") == "completed":
            manifest = client.get_manifest(trace_id)
            print(f"\nManifest 包含 {len(manifest)} 个工作项")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    # 如果提供了 trace_id 作为参数，则只检查状态
    if len(sys.argv) > 1:
        trace_id = sys.argv[1]
        test_quick_status_check(trace_id)
    else:
        # 否则运行完整测试
        test_full_workflow()

