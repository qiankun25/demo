"""Discovery Query API (strict microservices migration).

This API exposes read-only access to discovery results so the orchestrator can fan-out
without relying on shared global storage semantics.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    discovery_database_url: str = "postgresql://discovery_user:discovery_pass@localhost:5434/discovery"

    class Config:
        env_prefix = "DISCOVERY_"
        case_sensitive = False


settings = Settings()


def _ensure_contracts_on_path() -> None:
    # Make `nexus_sdk` and optional shared libs importable when running from repo.
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    for p in [os.path.join(root, "nexus_sdk"), os.path.join(root, "tool_services", "libs", "contracts")]:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


_ensure_contracts_on_path()

from nexus_sdk.common import MockStorage  # noqa: E402
from app.db import DiscoveryDB  # noqa: E402


db = DiscoveryDB.from_url(settings.discovery_database_url)
# P0: schema must be managed by migrations job (Alembic), not at app startup.


app = FastAPI(title="Discovery Service API", version="0.1.0")


@app.get("/health")
async def health():
    # Human-friendly aggregated health (do not use for K8s probes; use /health/live and /health/ready)
    ready = await health_ready()
    code = ready.status_code
    payload = ready.body
    # FastAPI JSONResponse.body is bytes; decode best-effort
    try:
        import json

        shaped = json.loads(payload.decode("utf-8"))
    except Exception:
        shaped = {"status": "unknown", "raw": str(payload)}
    shaped.setdefault("service", "discovery_service")
    shaped.setdefault("timestamp", time.time())
    return JSONResponse(status_code=code, content=shaped)


@app.get("/health/live")
async def health_live():
    """Liveness probe: process is up."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe: critical dependencies reachable (DB + MinIO claim-check)."""
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

    # Claim-check storage connectivity (MinIO) - best-effort
    try:
        # This ensures bucket exists and can list objects (may be empty).
        await MockStorage.list_keys(prefix="")
        components["storage"] = "ok"
    except Exception as e:
        ok = False
        components["storage"] = f"error: {e}"

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})


class DiscoveryResultResponse(BaseModel):
    result_id: str
    data: Dict[str, Any]

class DiscoveryMinFieldsItem(BaseModel):
    title: Optional[str] = None
    authors: list[str] = []
    pdf_url: Optional[str] = None
    canonical_id: Optional[str] = None
    doi: Optional[str] = None
    publication_date: Optional[str] = None


class DiscoveryMinFieldsResponse(BaseModel):
    result_id: str
    items: list[DiscoveryMinFieldsItem]


@app.get("/v1/results/{result_id}", response_model=DiscoveryResultResponse)
async def get_result(result_id: str):
    output_key = db.get_output_key(result_id)
    if not output_key:
        raise HTTPException(status_code=404, detail="result not found")
    data = await MockStorage.get(output_key)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid stored result")
    return DiscoveryResultResponse(result_id=result_id, data=data)


@app.get("/v1/results/{result_id}/min_fields", response_model=DiscoveryMinFieldsResponse)
async def get_min_fields(result_id: str, limit: int = 50):
    output_key = db.get_output_key(result_id)
    if not output_key:
        raise HTTPException(status_code=404, detail="result not found")
    data = await MockStorage.get(output_key)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid stored result")
    results = data.get("results") or []
    if not isinstance(results, list):
        results = []
    out: list[DiscoveryMinFieldsItem] = []
    for r in results[: max(1, min(limit, 200))]:
        if not isinstance(r, dict):
            continue
        pdf_url = str(r.get("pdf_url") or "").strip() or None
        doi = str(r.get("doi") or "").strip() or None
        canonical_id = str(r.get("id") or "").strip() or None
        out.append(
            DiscoveryMinFieldsItem(
                title=str(r.get("title") or r.get("display_name") or "").strip() or None,
                authors=[str(a) for a in (r.get("authors") or []) if str(a).strip()],
                pdf_url=pdf_url,
                canonical_id=canonical_id,
                doi=doi,
                publication_date=str(r.get("publication_date") or "").strip() or None,
            )
        )
    return DiscoveryMinFieldsResponse(result_id=result_id, items=out)


