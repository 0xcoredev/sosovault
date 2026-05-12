"""
SoSoValue OpenAPI client.

Docs: https://sosovalue-1.gitbook.io/sosovalue-api-doc

All requests carry the `x-soso-api-key` header. Endpoints we use:

- `GET /indices`                                    list of index tickers
- `GET /indices/{ticker}/constituents`              list of {currency_id, symbol, weight}
- `GET /indices/{ticker}/market-snapshot`           {price, 24h_change_pct, 7day_roi, 1month_roi, 1year_roi}
- `GET /etfs`                                       list of {ticker, name, exchange}
- `GET /etfs/{ticker}/market-snapshot`              {net_inflow, cum_inflow, mkt_price, ...}
- `GET /currencies/{currency_id}/market-snapshot`   {price, change_pct_24h, marketcap, ...}
- `GET /news`                                       paged news feed

The client caches index lists and snapshots in-process for `CACHE_TTL_S` seconds so we
do not hammer the API while the user is clicking around. If a request fails (key missing,
rate limited, network error), the helper methods return `None` / `[]` so callers can fall
back to fixtures and the demo never breaks.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

BASE_URL = os.getenv("SOSOVALUE_BASE_URL", "https://openapi.sosovalue.com/openapi/v1")
API_KEY = os.getenv("SOSOVALUE_API_KEY", "")
CACHE_TTL_S = int(os.getenv("SOSOVALUE_CACHE_TTL_S", "60"))
TIMEOUT_S = float(os.getenv("SOSOVALUE_TIMEOUT_S", "8"))


class _Cache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        ts, value = item
        if time.time() - ts > CACHE_TTL_S:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)


_cache = _Cache()


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["x-soso-api-key"] = API_KEY
    return headers


async def _get(path: str, params: Optional[dict[str, Any]] = None) -> Optional[Any]:
    """Internal GET with caching + best-effort error handling."""
    cache_key = f"{path}::{params or {}}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    if not API_KEY:
        # No key -> never call upstream. Caller falls back.
        return None

    url = f"{BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(url, headers=_headers(), params=params or {})
            resp.raise_for_status()
            data = resp.json()
            _cache.set(cache_key, data)
            return data
    except httpx.HTTPStatusError as exc:
        print(f"[sosovalue] HTTP {exc.response.status_code} on {path}: {exc.response.text[:200]}")
    except httpx.HTTPError as exc:
        print(f"[sosovalue] network error on {path}: {exc}")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[sosovalue] unexpected error on {path}: {exc}")
    return None


# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #

async def list_indices() -> list[str]:
    """Returns ticker strings, e.g. ['ssimag7', 'ssilayer1']. Empty list on failure."""
    data = await _get("/indices")
    if isinstance(data, list):
        return [str(t) for t in data if t]
    return []


async def index_constituents(ticker: str) -> list[dict[str, Any]]:
    """Returns [{currency_id, symbol, weight}, ...]."""
    data = await _get(f"/indices/{ticker}/constituents")
    if isinstance(data, list):
        return data
    return []


async def index_snapshot(ticker: str) -> Optional[dict[str, Any]]:
    """Returns {price, 24h_change_pct, 7day_roi, 1month_roi, 1year_roi, ...}."""
    return await _get(f"/indices/{ticker}/market-snapshot")


async def list_etfs() -> list[dict[str, Any]]:
    """Returns [{ticker, name, exchange}, ...]."""
    data = await _get("/etfs")
    if isinstance(data, list):
        return data
    return []


async def etf_snapshot(ticker: str) -> Optional[dict[str, Any]]:
    """Returns {date, ticker, net_inflow, cum_inflow, mkt_price, ...}."""
    return await _get(f"/etfs/{ticker}/market-snapshot")


async def currency_snapshot(currency_id: str) -> Optional[dict[str, Any]]:
    """Returns {price, change_pct_24h, marketcap, ...}."""
    return await _get(f"/currencies/{currency_id}/market-snapshot")


async def news(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Returns {page, page_size, total, list:[{id, title, release_time, source_link, content}]}."""
    data = await _get("/news", params={"page": page, "page_size": page_size})
    if isinstance(data, dict):
        return data
    return {"page": page, "page_size": page_size, "total": 0, "list": []}
