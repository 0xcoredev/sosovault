"""
SoDEX read-only client (testnet by default).

Docs: https://sodex.com/documentation/api/api

Uses public, unauthenticated endpoints to fetch live orderbook prices.
Order placement with EIP-712 signing is handled by services.eip712.

Endpoint we use:

  GET /api/v1/spot/markets/bookTickers?symbol={symbol}

Sample response:

  {
    "code": 0,
    "timestamp": 1767501757000,
    "data": [
      { "symbol": "vBTC_vUSDC", "bidPx": "99165", "bidSz": "...",
        "askPx": "99380", "askSz": "..." }
    ]
  }
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .logging import get_logger

log = get_logger("sodex")

# Default to testnet for the buildathon. Override with SODEX_BASE_URL for mainnet.
BASE_URL = os.getenv("SODEX_BASE_URL", "https://testnet-gw.sodex.dev")
TIMEOUT_S = float(os.getenv("SODEX_TIMEOUT_S", "5"))
CACHE_TTL_S = int(os.getenv("SODEX_CACHE_TTL_S", "10"))

_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Optional[Any]:
    item = _cache.get(key)
    if item is None:
        return None
    ts, value = item
    if time.time() - ts > CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


async def book_ticker(symbol: str) -> Optional[dict[str, Any]]:
    """Returns the best bid / ask for a SoDEX symbol, or None on failure.

    Symbols on testnet look like ``vBTC_vUSDC``. The returned dict has
    ``symbol``, ``bidPx``, ``bidSz``, ``askPx``, ``askSz``, ``fetchedAt``.
    """
    cache_key = f"book_ticker::{symbol}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BASE_URL}/api/v1/spot/markets/bookTickers"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(url, params={"symbol": symbol})
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        log.warning("%s bookTicker error: %s", symbol, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        log.error("%s unexpected error: %s", symbol, exc)
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("code") not in (0, "0", None):
        # Non-zero code means SoDEX rejected the query.
        return None

    data = payload.get("data") or []
    if not data:
        return None
    row = data[0]
    out = {
        "symbol": row.get("symbol", symbol),
        "bidPx": row.get("bidPx", ""),
        "bidSz": row.get("bidSz", ""),
        "askPx": row.get("askPx", ""),
        "askSz": row.get("askSz", ""),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }
    _cache_set(cache_key, out)
    return out


async def quote_basket(symbols: list[str]) -> list[dict[str, Any]]:
    """Best-effort fetch of bookTickers for a list of SoDEX symbols.

    Returns one entry per symbol. Failed lookups are returned as a stub so the UI
    can still render the basket without flickering.
    """
    out: list[dict[str, Any]] = []
    for sym in symbols:
        ticker = await book_ticker(sym)
        if ticker is None:
            out.append(
                {
                    "symbol": sym,
                    "bidPx": "",
                    "bidSz": "",
                    "askPx": "",
                    "askSz": "",
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "stub": True,
                }
            )
        else:
            out.append(ticker)
    return out
