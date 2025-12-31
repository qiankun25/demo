"""
测试特定 trace_id 的数据访问
使用已知的 trace_id 测试各种 storage_key 的访问
"""

import requests
import urllib.parse
import json
import os
from pathlib import Path


class NexusDataTester:
    """测试 Nexus 数据访问"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = f"{base_url}/api/v1"
        self.session = requests.Session()
        self.session.timeout = 30
    
    def test_trace_id(self, trace_id: str):
        """测试指定 trace_id 的完整数据访问流程"""
        # 1. 获取任务状态
        status = self._get_job_status(trace_id)
        
        if not status:
            print(f"❌ 任务不存在: {trace_id}")
            return False
        
        # 2. 打印搜索结果 (Search Results)
        artifacts = status.get("artifacts", {})
        search_results_key = artifacts.get("search_results")
        if search_results_key:
            print("\n" + "=" * 20 + " 搜索结果 (Search Results) " + "=" * 20)
            try:
                # search_results_key 可能是一个 URL 或者 storage_key
                if search_results_key.startswith("/"):
                    url = f"{self.base_url}{search_results_key}"
                    search_data = self.session.get(url).json()
                else:
                    search_data = self._get_artifact_data(trace_id, search_results_key)
                
                print(json.dumps(search_data, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"获取搜索结果失败: {e}")
        
        # 3. 获取 Manifest 并打印 Parse 结果
        manifest = self._get_manifest(trace_id, status)
        
        if not manifest:
            print("❌ 无法获取 Manifest")
            return False
        
        print("\n" + "=" * 20 + " 文档解析结果 (Parse Results) " + "=" * 20)
        for idx, item in enumerate(manifest, 1):
            parse_key = item.get('parse_key')
            if parse_key:
                print(f"\n--- 工作项 {idx} ({item.get('work_key', 'unknown')}) ---")
                try:
                    parse_data = self._get_artifact_data(trace_id, parse_key)
                    print(json.dumps(parse_data, indent=2, ensure_ascii=False))
                except Exception as e:
                    print(f"获取解析结果失败 ({parse_key}): {e}")
        
        return True
    
    def _get_job_status(self, trace_id: str):
        """获取任务状态"""
        try:
            url = f"{self.api_prefix}/jobs/{trace_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取状态失败: {e}")
            return None
    
    def _get_manifest(self, trace_id: str, status: dict):
        """获取 Manifest"""
        # 方式 1: 从 artifacts 获取
        artifacts = status.get("artifacts", {})
        manifest_url = artifacts.get("detailed_manifest")
        
        if manifest_url:
            try:
                if manifest_url.startswith("/"):
                    manifest_url = f"{self.base_url}{manifest_url}"
                response = self.session.get(manifest_url)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"从 artifacts URL 获取失败: {e}")
        
        # 方式 2: 使用 fallback storage_key
        print("尝试使用 fallback storage_key...")
        fallback_key = f"data:manifest:{trace_id}"
        try:
            return self._get_artifact_data(trace_id, fallback_key)
        except Exception as e:
            print(f"从 fallback storage_key 获取失败: {e}")
            return None
    
    def _unwrap_claimcheck(self, raw: bytes):
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
    
    def _get_artifact_data(self, trace_id: str, artifact_key: str):
        """获取 Artifact 数据"""
        # URL 编码
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
    
    def _test_artifact_access(self, trace_id: str, artifact_key: str, 
                            label: str, is_binary: bool = False, 
                            show_preview: bool = False):
        """测试单个 artifact 的访问"""
        print(f"\n  测试 {label}:")
        print(f"    Storage Key: {artifact_key[:80]}...")
        
        try:
            data = self._get_artifact_data(trace_id, artifact_key)
            
            if is_binary:
                # 二进制数据（如 PDF）
                size_kb = len(data) / 1024
                print(f"    ✓ 成功获取二进制数据")
                print(f"    大小: {size_kb:.2f} KB")
                
                # 检查是否是 PDF
                if isinstance(data, bytes) and data.startswith(b'%PDF'):
                    print(f"    类型: PDF 文件")
                else:
                    print(f"    类型: 二进制数据（前16字节: {data[:16]}）")
            else:
                # JSON 数据
                if isinstance(data, dict):
                    print(f"    ✓ 成功获取 JSON 数据")
                    print(f"    字段数: {len(data)}")
                    print(f"    顶层字段: {list(data.keys())}")
                    
                    if show_preview:
                        # 显示数据预览
                        if 'title' in data:
                            print(f"    标题: {data['title']}")
                        if 'llm_summary' in data:
                            summary = data['llm_summary']
                            preview = summary[:100] + "..." if len(summary) > 100 else summary
                            print(f"    摘要预览: {preview}")
                        if 'chunks' in data:
                            print(f"    块数量: {len(data.get('chunks', []))}")
                elif isinstance(data, list):
                    print(f"    ✓ 成功获取 JSON 数组")
                    print(f"    元素数: {len(data)}")
                else:
                    print(f"    ✓ 成功获取数据")
                    print(f"    类型: {type(data)}")
            
            return True
            
        except requests.exceptions.HTTPError as e:
            print(f"    ✗ HTTP 错误: {e.response.status_code}")
            if e.response.status_code == 404:
                print(f"    原因: Artifact 不存在或未授权访问")
            else:
                print(f"    响应: {e.response.text[:200]}")
            return False
        except Exception as e:
            print(f"    ✗ 错误: {e}")
            return False
    
    def _test_download(self, trace_id: str, manifest: list):
        """测试文件下载功能"""
        if not manifest:
            print("  无可下载的文件")
            return
        
        # 创建下载目录
        download_dir = Path("downloads") / trace_id
        download_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"  下载目录: {download_dir}")
        
        # 下载第一个工作项的 parse 数据作为示例
        first_item = manifest[0]
        parse_key = first_item.get('parse_key')
        
        if not parse_key:
            print("  无可下载的数据")
            return
        
        try:
            print(f"\n  下载第一个工作项的解析数据...")
            data = self._get_artifact_data(trace_id, parse_key)
            
            # 根据数据类型保存文件
            if isinstance(data, (dict, list)):
                # JSON 数据
                filename = download_dir / "parse_data_0.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif isinstance(data, bytes):
                # 二进制数据，尝试解析为 JSON
                try:
                    # 尝试解码为文本并解析 JSON
                    text = data.decode('utf-8')
                    json_data = json.loads(text)
                    filename = download_dir / "parse_data_0.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # 无法解析为 JSON，保存为二进制文件
                    filename = download_dir / "parse_data_0.bin"
                    with open(filename, 'wb') as f:
                        f.write(data)
            else:
                # 其他类型，尝试转换为 JSON
                try:
                    filename = download_dir / "parse_data_0.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                except TypeError:
                    # 无法序列化，保存为文本
                    filename = download_dir / "parse_data_0.txt"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(str(data))
            
            file_size = os.path.getsize(filename)
            print(f"  ✓ 下载成功")
            print(f"    文件: {filename}")
            print(f"    大小: {file_size / 1024:.2f} KB")
            
            # 如果有 download_key，也尝试下载 PDF
            download_key = first_item.get('download_key')
            if download_key:
                print(f"\n  下载第一个工作项的 PDF 文件...")
                try:
                    pdf_data = self._get_artifact_data(trace_id, download_key)
                    pdf_filename = download_dir / "paper_0.pdf"
                    
                    with open(pdf_filename, 'wb') as f:
                        f.write(pdf_data)
                    
                    pdf_size = os.path.getsize(pdf_filename)
                    print(f"  ✓ PDF 下载成功")
                    print(f"    文件: {pdf_filename}")
                    print(f"    大小: {pdf_size / 1024:.2f} KB")
                except Exception as e:
                    print(f"  ✗ PDF 下载失败: {e}")
            
        except Exception as e:
            print(f"  ✗ 下载失败: {e}")


def main():
    """主函数"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="测试 Nexus API 的特定 trace_id 数据访问",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认 trace_id 和本地服务器
  python test_specific_trace.py
  
  # 指定 trace_id
  python test_specific_trace.py bd45a9af-bd5b-45b8-b547-c3125d574bad
  
  # 指定 trace_id 和服务器地址
  python test_specific_trace.py bd45a9af-bd5b-45b8-b547-c3125d574bad --url http://8.134.183.68:8000
  
  # 只指定服务器地址（使用默认 trace_id）
  python test_specific_trace.py --url http://localhost:8000
        """
    )
    
    parser.add_argument(
        "trace_id",
        nargs="?",
        default="bd45a9af-bd5b-45b8-b547-c3125d574bad",
        help="要测试的 trace_id（默认: bd45a9af-bd5b-45b8-b547-c3125d574bad）"
    )
    
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Nexus 服务器地址（默认: http://localhost:8000）"
    )
    
    args = parser.parse_args()
    
    trace_id = args.trace_id
    base_url = args.url
    
    print(f"服务器地址: {base_url}")
    print(f"Trace ID: {trace_id}")
    print(f"如需测试其他 trace_id 或服务器，请运行: python {sys.argv[0]} --help\n")
    
    tester = NexusDataTester(base_url=base_url)
    tester.test_trace_id(trace_id)


if __name__ == "__main__":
    main()

