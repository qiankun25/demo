import json
import logging
import os
import time
from typing import Any, Dict, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def _level() -> int:
    v = (os.getenv("PARSER_LOG_LEVEL") or "INFO").strip().upper()
    return getattr(logging, v, logging.INFO)


_LOGGER = logging.getLogger("paper_analyse.parser")
if not _LOGGER.handlers:
    _LOGGER.setLevel(_level())
    h = logging.StreamHandler()
    h.setLevel(_level())
    _LOGGER.addHandler(h)
    _LOGGER.propagate = False


def log_json(
    *,
    level: str,
    event: str,
    trace_id: Optional[str] = None,
    input_key: Optional[str] = None,
    doc_id: Optional[str] = None,
    fields: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "ts_ms": _now_ms(),
        "service": "paper_analyse.parser",
        "event": event,
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if input_key:
        payload["input_key"] = input_key
    if doc_id:
        payload["doc_id"] = doc_id
    if fields:
        for k, v in fields.items():
            if v is None:
                continue
            payload[k] = v
    msg = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    getattr(_LOGGER, level.lower(), _LOGGER.info)(msg)


