import asyncio
import random
import time
from typing import Any, Dict, Optional, Tuple, Set, List

import httpx

from tool_services.discovery_service.settings import settings

try:
    # optional: if redis is configured, use it for quota counters (cross-process)
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


_rate_lock = asyncio.Lock()
_rate_tokens: float = 0.0
_rate_last_ts: float = 0.0

_concurrency_lock = asyncio.Lock()
_concurrency_sem: Optional[asyncio.Semaphore] = None

_quota_lock = asyncio.Lock()
_quota_minute_window_start: float = 0.0
_quota_minute_count: int = 0
_quota_day_window_start: float = 0.0
_quota_day_count: int = 0

_redis_client: Optional["Redis"] = None


def _retryable_statuses() -> Set[int]:
    return set(settings.openalex_retryable_status_codes)


async def _maybe_limit_concurrency() -> Optional[asyncio.Semaphore]:
    """
    Concurrency limiter (process-local):
    - OPENALEX_MAX_CONCURRENCY: max in-flight OpenAlex requests
    """
    max_c = settings.openalex_max_concurrency
    if max_c <= 0:
        return None
    global _concurrency_sem
    async with _concurrency_lock:
        if _concurrency_sem is None or _concurrency_sem._value + len(_concurrency_sem._waiters) != max_c:  # type: ignore[attr-defined]
            # Re-init semaphore if first time; if config changes at runtime this may not perfectly track,
            # but it's good enough for a long-running worker with static env vars.
            _concurrency_sem = asyncio.Semaphore(max_c)
        return _concurrency_sem


async def _maybe_rate_limit() -> None:
    """
    Token bucket rate limiter (process-local):
    - OPENALEX_RATE_LIMIT_RPS: refill rate (tokens/sec)
    - OPENALEX_RATE_LIMIT_BURST: bucket capacity
    """
    rps = settings.openalex_rate_limit_rps
    burst = settings.openalex_rate_limit_burst
    if rps <= 0 or burst <= 0:
        return

    global _rate_tokens, _rate_last_ts
    async with _rate_lock:
        now = time.time()
        if _rate_last_ts <= 0:
            _rate_last_ts = now
            _rate_tokens = float(burst)

        dt = max(0.0, now - _rate_last_ts)
        _rate_last_ts = now
        _rate_tokens = min(float(burst), _rate_tokens + dt * rps)

        if _rate_tokens >= 1.0:
            _rate_tokens -= 1.0
            return

        need = 1.0 - _rate_tokens
        sleep_s = need / rps if rps > 0 else 0.0
        await asyncio.sleep(max(0.0, sleep_s))
        # consume token pessimistically
        _rate_last_ts = time.time()
        _rate_tokens = max(0.0, _rate_tokens + sleep_s * rps - 1.0)


async def _get_redis() -> Optional["Redis"]:
    global _redis_client
    if not settings.redis_connection_url:
        return None
    if Redis is None:
        return None
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_connection_url, encoding=None, decode_responses=False)
    return _redis_client


async def _maybe_enforce_quota() -> None:
    """
    Quota limiter:
    - OPENALEX_QUOTA_PER_MINUTE / OPENALEX_QUOTA_PER_DAY
    If REDIS_URL configured, use Redis INCR with expiry for cross-process stability;
    otherwise fallback to in-memory counters.
    """
    per_min = settings.openalex_quota_per_minute
    per_day = settings.openalex_quota_per_day
    if per_min <= 0 and per_day <= 0:
        return

    now = time.time()
    r = await _get_redis()
    if r is not None:
        minute_key = f"nexus:openalex:quota:minute:{int(now // 60)}"
        day_key = f"nexus:openalex:quota:day:{int(now // 86400)}"
        try:
            if per_min > 0:
                v = await r.incr(minute_key)
                await r.expire(minute_key, 120)
                if int(v) > per_min:
                    raise RuntimeError(f"OpenAlex quota exceeded: per_minute>{per_min}")
            if per_day > 0:
                v = await r.incr(day_key)
                await r.expire(day_key, 2 * 86400)
                if int(v) > per_day:
                    raise RuntimeError(f"OpenAlex quota exceeded: per_day>{per_day}")
            return
        except Exception:
            # fallback to in-memory if redis fails
            pass

    global _quota_minute_window_start, _quota_minute_count, _quota_day_window_start, _quota_day_count
    async with _quota_lock:
        if per_min > 0:
            if _quota_minute_window_start <= 0 or (now - _quota_minute_window_start) >= 60:
                _quota_minute_window_start = now
                _quota_minute_count = 0
            _quota_minute_count += 1
            if _quota_minute_count > per_min:
                raise RuntimeError(f"OpenAlex quota exceeded: per_minute>{per_min}")

        if per_day > 0:
            if _quota_day_window_start <= 0 or (now - _quota_day_window_start) >= 86400:
                _quota_day_window_start = now
                _quota_day_count = 0
            _quota_day_count += 1
            if _quota_day_count > per_day:
                raise RuntimeError(f"OpenAlex quota exceeded: per_day>{per_day}")


def _retry_after_seconds(resp: httpx.Response) -> Optional[float]:
    try:
        ra = (resp.headers.get("retry-after") or "").strip()
        if not ra:
            return None
        return float(ra)
    except Exception:
        return None


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
    base = settings.openalex_base.rstrip("/") + settings.openalex_works_path
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
    对“可重试错误”做指数退避（可配置），并支持限流/配额。
    返回：(data, debug_meta)
    """
    headers = {"User-Agent": settings.openalex_user_agent}
    last_err: Optional[Exception] = None
    last_status: Optional[int] = None
    retryable = _retryable_statuses()

    for attempt in range(settings.openalex_max_retries):
        try:
            await _maybe_rate_limit()
            await _maybe_enforce_quota()
            sem = await _maybe_limit_concurrency()
            if sem is None:
                async with httpx.AsyncClient(timeout=settings.openalex_timeout_s) as client:
                    resp = await client.get(url, headers=headers)
            else:
                async with sem:
                    async with httpx.AsyncClient(timeout=settings.openalex_timeout_s) as client:
                        resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                try:
                    return resp.json(), {
                        "http_status": resp.status_code,
                        "retry_count": attempt,
                        "error_category": "",
                    }
                except Exception as e:
                    # Rare: transient gateway/proxy returning HTML with 200; treat as retryable
                    last_err = e
                    await _sleep_backoff(attempt)
                    continue

            last_status = resp.status_code
            # Error classification:
            # - 429: rate limited (retryable, honor Retry-After)
            # - retryable status list (defaults include 5xx/408): retryable
            # - other 4xx: non-retryable
            if resp.status_code == 429:
                ra = _retry_after_seconds(resp)
                if ra is not None and ra > 0:
                    await asyncio.sleep(min(settings.openalex_backoff_max_s, ra))
                else:
                    await _sleep_backoff(attempt)
                last_err = RuntimeError(f"OpenAlex HTTP 429 rate_limited")
                continue
            if resp.status_code in retryable or (500 <= resp.status_code <= 599):
                await _sleep_backoff(attempt)
                last_err = RuntimeError(f"OpenAlex HTTP {resp.status_code} retryable")
                continue
            if 400 <= resp.status_code <= 499:
                # Do NOT retry other 4xx
                try:
                    resp.raise_for_status()
                finally:
                    pass

            resp.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_err = e
            await _sleep_backoff(attempt)
            continue
        except Exception as e:
            last_err = e
            break

    raise RuntimeError(f"OpenAlex request failed after retries. url={url} http_status={last_status} err={last_err}")


async def _sleep_backoff(attempt: int) -> None:
    base = settings.openalex_backoff_base_s * (2**attempt)
    max_s = settings.openalex_backoff_max_s
    jitter_ratio = settings.openalex_backoff_jitter_ratio
    base = min(max_s, base)
    jitter = random.random() * max(0.0, jitter_ratio) * base
    await asyncio.sleep(min(max_s, base + jitter))

