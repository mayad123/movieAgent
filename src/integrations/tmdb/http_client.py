"""
Shared synchronous HTTP client for TMDB API calls (connection pooling, keep-alive).

Used by resolver, image_config, and movie_metadata. Prefer tmdb_request_json() for GET JSON.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def get_sync_client() -> httpx.Client:
    """Thread-safe singleton Client with connection limits for burst TMDB traffic."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
                follow_redirects=True,
            )
        return _client


def close_sync_client() -> None:
    """Close pooled client (tests / process teardown)."""
    global _client
    with _client_lock:
        if _client is not None:
            with contextlib.suppress(Exception):
                _client.close()
            _client = None


def tmdb_request_json(
    url: str,
    token: str,
    *,
    timeout: float = 10.0,
    log_label: str = "TMDB",
) -> Any | None:
    """
    GET JSON from TMDB. Returns parsed dict/list or None on failure.
    Token must not be logged.
    """
    tok = (token or "").strip()
    if not tok:
        return None
    headers = {"Accept": "application/json", "Authorization": f"Bearer {tok}"}
    t0 = time.perf_counter()
    try:
        client = get_sync_client()
        resp = client.get(url, headers=headers, timeout=max(1.0, timeout))
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        safe_url = url.split("?")[0]
        if len(safe_url) > 96:
            safe_url = safe_url[:96] + "…"
        logger.debug("%s GET ok ms=%.1f url=%s", log_label, elapsed_ms, safe_url)
        return resp.json()
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug("%s GET failed ms=%.1f err=%s", log_label, elapsed_ms, e)
        return None


__all__ = ["close_sync_client", "get_sync_client", "tmdb_request_json"]
