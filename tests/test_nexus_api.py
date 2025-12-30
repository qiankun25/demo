"""
简单的 Nexus API 测试脚本

提交两个任务（MORNING_REPORT 和 SUMMARY_REPORT）并打印返回结果
使用新的统一报告 API

用法:
    python tests/test_nexus_api.py
"""

import requests
import time
import json
from typing import Dict, Any

# 配置
NEXUS_URL = "http://localhost:8000/api/v1"
POLL_INTERVAL = 5  # 轮询间隔（秒）
MAX_WAIT_TIME = 600  # 最大等待时间（秒），10分钟


def submit_job(task_type: str, parameters: Dict[str, Any]) -> str:
    """提交任务到 Nexus"""
    print(f"\n[提交任务] task_type={task_type}")
    print(f"  参数: {json.dumps(parameters, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            f"{NEXUS_URL}/jobs",
            json={
                "task_type": task_type,
                "parameters": parameters
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        trace_id = result["trace_id"]
        print(f"  [成功] trace_id={trace_id}")
        return trace_id
    except requests.exceptions.ConnectionError:
        print(f"  [错误] 无法连接到 Nexus ({NEXUS_URL})")
        print(f"  请确认服务已启动: docker-compose ps nexus")
        raise
    except Exception as e:
        print(f"  [错误] 提交失败: {e}")
        raise


def wait_for_completion(trace_id: str) -> bool:
    """等待任务完成"""
    print(f"\n[轮询状态] trace_id={trace_id}")
    status_url = f"{NEXUS_URL}/jobs/{trace_id}"
    start_time = time.time()
    iteration = 0
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > MAX_WAIT_TIME:
            print(f"  [超时] 任务超过 {MAX_WAIT_TIME} 秒未完成")
            return False
        
        try:
            response = requests.get(status_url, timeout=30)
            response.raise_for_status()
            status = response.json()
            
            current_status = status.get("status", "unknown")
            completed = status.get("completed_count", 0)
            total = status.get("total_work_items", 0)
            failed = status.get("failed_count", 0)
            
            iteration += 1
            print(f"  [{int(elapsed)}s | #{iteration}] status={current_status}, "
                  f"completed={completed}/{total}, failed={failed}")
            
            if current_status == "completed":
                print(f"  [完成] 任务已成功完成")
                return True
            
            if current_status == "failed":
                print(f"  [失败] 任务执行失败")
                failures = status.get("failures", [])
                if failures:
                    print(f"  失败详情: {json.dumps(failures, indent=2, ensure_ascii=False)}")
                return False
            
            time.sleep(POLL_INTERVAL)
            
        except Exception as e:
            print(f"  [警告] 查询状态失败: {e}")
            time.sleep(POLL_INTERVAL)
            continue


def get_report(trace_id: str) -> Dict[str, Any]:
    """获取标准化报告"""
    print(f"\n[获取报告] trace_id={trace_id}")
    
    try:
        response = requests.get(
            f"{NEXUS_URL}/jobs/{trace_id}/report",
            timeout=60
        )
        response.raise_for_status()
        report = response.json()
        print(f"  [成功] 获取到报告")
        return report
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            print(f"  [错误] 任务尚未完成: {e.response.json().get('detail', '')}")
        else:
            print(f"  [错误] HTTP {e.response.status_code}: {e.response.text}")
        raise
    except Exception as e:
        print(f"  [错误] 获取报告失败: {e}")
        raise


def print_report(report: Dict[str, Any]):
    """打印报告内容"""
    task_type = report.get("task_type", "UNKNOWN")
    trace_id = report.get("trace_id", "")
    
    print(f"\n{'='*80}")
    print(f"报告内容 - task_type={task_type}, trace_id={trace_id}")
    print(f"{'='*80}")
    
    if task_type == "MORNING_REPORT":
        print(f"\n任务类型: MORNING_REPORT")
        print(f"请求数量: {report.get('requested_limit', 0)}")
        print(f"论文数量: {report.get('paper_count', 0)}")
        print(f"失败数量: {report.get('failure_count', 0)}")
        
        papers = report.get("papers", [])
        if papers:
            print(f"\n论文列表:")
            for i, paper in enumerate(papers, 1):
                paper_info = paper.get("paper", {})
                summary = paper.get("summary", {})
                print(f"\n  [{i}] {paper_info.get('title', 'Unknown')}")
                print(f"      Authors: {', '.join(paper_info.get('authors', [])) or 'N/A'}")
                print(f"      PDF URL: {paper_info.get('pdf_url', 'N/A')}")
                print(f"      Summary: {summary.get('llm_summary', 'N/A')[:100]}...")
        
        failures = report.get("failures", [])
        if failures:
            print(f"\n失败列表:")
            for failure in failures:
                print(f"  - {failure.get('work_key', 'Unknown')}: {failure.get('error_msg', 'N/A')}")
        
        input_info = report.get("input", {})
        if input_info:
            print(f"\n输入信息:")
            print(f"  Query: {input_info.get('query', 'N/A')}")
            print(f"  Filters: {json.dumps(input_info.get('filters', {}), ensure_ascii=False)}")
    
    elif task_type == "SUMMARY_REPORT":
        print(f"\n任务类型: SUMMARY_REPORT")
        print(f"论文数量: {report.get('paper_count', 0)}")
        
        overview_md = report.get("overview_md")
        if overview_md:
            print(f"\n综述内容 ({len(overview_md)} 字符):")
            print(f"{'-'*80}")
            print(overview_md)
            print(f"{'-'*80}")
        
        meta = report.get("meta", {})
        if meta:
            print(f"\n元数据:")
            print(f"  Model: {meta.get('model', 'N/A')}")
            print(f"  Domain: {meta.get('domain', 'N/A')}")
            print(f"  Style: {meta.get('style', 'N/A')}")
    
    print(f"\n{'='*80}\n")


def test_morning_report():
    """测试 MORNING_REPORT 任务"""
    print("\n" + "="*80)
    print("测试 1: MORNING_REPORT")
    print("="*80)
    
    try:
        # 提交任务
        trace_id = submit_job(
            "MORNING_REPORT",
            {
                "limit": 3,
                "query": "large language model",
                "filters": {
                    "publication_year": "2024"
                }
            }
        )
        
        # 等待完成
        if not wait_for_completion(trace_id):
            print("[测试1失败] 任务未完成")
            return False
        
        # 获取报告
        report = get_report(trace_id)
        
        # 打印报告
        print_report(report)
        
        print("[测试1成功] MORNING_REPORT 测试完成\n")
        return True
        
    except Exception as e:
        print(f"[测试1失败] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summary_report():
    """测试 SUMMARY_REPORT 任务"""
    print("\n" + "="*80)
    print("测试 2: SUMMARY_REPORT")
    print("="*80)
    
    try:
        # 提交任务（使用示例 papers 数据）
        trace_id = submit_job(
            "SUMMARY_REPORT",
            {
                "papers": [
                    {
                        "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
                        "title": "Sample Paper 1",
                        "authors": ["Author A", "Author B"]
                    },
                    {
                        "pdf_url": "https://arxiv.org/pdf/2301.00002.pdf",
                        "title": "Sample Paper 2",
                        "authors": ["Author C", "Author D"]
                    }
                ],
                "domain": "machine_learning",
                "style": "academic"
            }
        )
        
        # 等待完成
        if not wait_for_completion(trace_id):
            print("[测试2失败] 任务未完成")
            return False
        
        # 获取报告
        report = get_report(trace_id)
        
        # 打印报告
        print_report(report)
        
        print("[测试2成功] SUMMARY_REPORT 测试完成\n")
        return True
        
    except Exception as e:
        print(f"[测试2失败] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*80)
    print("Nexus API 测试脚本")
    print("="*80)
    print(f"Nexus URL: {NEXUS_URL}")
    print(f"轮询间隔: {POLL_INTERVAL} 秒")
    print(f"最大等待: {MAX_WAIT_TIME} 秒")
    
    results = []
    
    # 测试1: MORNING_REPORT
    results.append(("MORNING_REPORT", test_morning_report()))
    
    # 测试2: SUMMARY_REPORT
    results.append(("SUMMARY_REPORT", test_summary_report()))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试汇总")
    print("="*80)
    for name, success in results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{name}: {status}")
    
    all_success = all(result[1] for result in results)
    print("="*80)
    if all_success:
        print("所有测试通过！")
    else:
        print("部分测试失败")
    print("="*80 + "\n")
    
    return 0 if all_success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消测试")
        exit(1)
    except Exception as e:
        print(f"\n[错误] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


