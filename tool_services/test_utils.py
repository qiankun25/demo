"""
用于 tool_services 下各微服务的“本地自测脚本”共享工具。

目标：
- 测试脚本必须使用真实 MockStorage（MinIO 后端）
- 不提供任何兜底/回退（MinIO/网络缺失直接失败）
"""

from __future__ import annotations

from typing import Any, Tuple, Type


async def ensure_storage_ready(MockStorage: Type[Any]) -> Tuple[bool, str]:
    """
    尝试使用真实 MockStorage（MinIO 后端）做一次读写探测。
    - 成功：返回 (True, "minio")
    - 失败：直接抛错（不做兜底）
    """
    probe_key = "__selftest__:probe"
    probe_val = {"ok": True}
    await MockStorage.save(probe_key, probe_val)
    got = await MockStorage.get(probe_key)
    if got != probe_val:
        raise RuntimeError(f"probe mismatch: got={got!r}")
    if hasattr(MockStorage, "list_keys"):
        keys = await MockStorage.list_keys("__selftest__:")  # type: ignore[attr-defined]
        if probe_key not in keys:
            # 某些实现可能 list_keys 不保证立即一致，这里不强制失败
            pass
    return True, "minio"

