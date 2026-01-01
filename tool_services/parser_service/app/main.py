from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.settings import settings
from app.db import ParserDB


def _ensure_nexus_sdk_on_path() -> None:
    # Needed to read legacy claimcheck keys during migration.
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    p = os.path.join(root, "nexus_sdk")
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)


_ensure_nexus_sdk_on_path()

from nexus_sdk.common import MockStorage  # noqa: E402


db = ParserDB.from_url(settings.database_url)
# P0: schema must be managed by migrations job (Alembic), not at app startup.

app = FastAPI(title="Parser Service", version="0.1.0")


@app.get("/health")
async def health():
    ready = await health_ready()
    code = ready.status_code
    payload = ready.body
    try:
        import json

        shaped = json.loads(payload.decode("utf-8"))
    except Exception:
        shaped = {"status": "unknown", "raw": str(payload)}
    shaped.setdefault("service", "parser_service")
    shaped.setdefault("timestamp", time.time())
    return JSONResponse(status_code=code, content=shaped)


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    components: Dict[str, Any] = {}
    ok = True

    # DB connectivity
    try:
        with db.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        components["database"] = "ok"
    except Exception as e:
        ok = False
        components["database"] = f"error: {e}"

    # Claim-check storage connectivity (MinIO)
    try:
        await MockStorage.list_keys(prefix="")
        components["storage"] = "ok"
    except Exception as e:
        ok = False
        components["storage"] = f"error: {e}"

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})


class ParsedDocResponse(BaseModel):
    doc_id: str
    data: Dict[str, Any]


@app.get("/v1/parsed/{doc_id}", response_model=ParsedDocResponse)
async def get_parsed(doc_id: str):
    output_key = db.get_output_key(doc_id)
    if not output_key:
        raise HTTPException(status_code=404, detail="doc not found")
    data = await MockStorage.get(output_key)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid parsed payload")
    return ParsedDocResponse(doc_id=doc_id, data=data)


