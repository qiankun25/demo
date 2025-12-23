import asyncio
import random
from typing import Any, Dict, Optional, Tuple

import httpx

from . import config


def build_works_url(
    *,
    search: str,
    filter_str: str,
    per_page: int,
    sample: Optional[int] = None,
    seed: Optional[int] = None,
    select: Optional[str] = None,
    mailto: Optional[str] = None,
) -> str:
    base = config.OPENALEX_BASE.rstrip("/") + config.OPENALEX_WORKS_PATH
    params: Dict[str, Any] = {"per-page": per_page}
    if search:
        params["search"] = search
    if filter_str:
        params["filter"] = filter_str
    if sample is not None:
        params["sample"] = sample
    if seed is not None:
        params["seed"] = seed
    if select:
        params["select"] = select
    if mailto:
        params["mailto"] = mailto
    return str(httpx.URL(base, params=params))


async def fetch_json_with_retry(url: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    对 429/5xx/timeout 做指数退避重试。
    返回：(data, debug_meta)
    """
    headers = {"User-Agent": config.OPENALEX_USER_AGENT}
    last_err: Optional[Exception] = None

    for attempt in range(config.OPENALEX_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=config.OPENALEX_TIMEOUT_S) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json(), {
                    "http_status": resp.status_code,
                    "retry_count": attempt,
                }

            # 可重试状态码
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = RuntimeError(f"OpenAlex HTTP {resp.status_code}")
                await _sleep_backoff(attempt)
                continue

            resp.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = e
            await _sleep_backoff(attempt)
            continue
        except Exception as e:
            last_err = e
            break

    raise RuntimeError(f"OpenAlex request failed after retries. url={url} err={last_err}")


async def _sleep_backoff(attempt: int) -> None:
    base = config.OPENALEX_BACKOFF_BASE_S * (2**attempt)
    jitter = random.random() * 0.2 * base
    await asyncio.sleep(base + jitter)

