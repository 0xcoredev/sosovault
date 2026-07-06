"""
SoDEX EIP-712 execution client (Wave 2).

Signs and submits spot orders to the SoDEX testnet REST API using EIP-712
non-custodial signing. The private key never leaves the backend.

Signing flow (per SoDEX docs):
  1. Build the order body in Go struct field order
  2. Compute payloadHash = keccak256(JSON({type: actionName, params: body}))
  3. Sign EIP-712 typed data: ExchangeAction { payloadHash, nonce }
  4. Wire format: 0x01 + r(32) + s(32) + v(0|1)  — v normalized 27/28 → 0/1
  5. Send with headers: X-API-Sign, X-API-Nonce, X-API-Chain

Env vars:
  SODEX_PRIVATE_KEY   — hex private key (0x...)
  SODEX_ADDRESS       — wallet address
  SODEX_ACCOUNT_ID    — numeric SoDEX account ID
  SODEX_CHAIN_ID      — 138565 (testnet) or 286623 (mainnet)
  SODEX_BASE_URL      — gateway URL (default testnet)
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import httpx
from eth_account import Account

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SODEX_PRIVATE_KEY = os.getenv("SODEX_PRIVATE_KEY", "")
SODEX_ADDRESS = os.getenv("SODEX_ADDRESS", "")
SODEX_ACCOUNT_ID = int(os.getenv("SODEX_ACCOUNT_ID", "0"))
SODEX_CHAIN_ID = int(os.getenv("SODEX_CHAIN_ID", "138565"))
SODEX_BASE_URL = os.getenv("SODEX_BASE_URL", "https://testnet-gw.sodex.dev/api/v1")
SODEX_TIMEOUT_S = float(os.getenv("SODEX_TIMEOUT_S", "15"))

# EIP-712 domain and types
_DOMAIN = {
    "name": "spot",
    "version": "1",
    "chainId": SODEX_CHAIN_ID,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "ExchangeAction": [
        {"name": "payloadHash", "type": "bytes32"},
        {"name": "nonce", "type": "uint64"},
    ],
}

_nonce_counter: int = 0
_wallet: Optional[Account] = None


def _get_wallet() -> Optional[Account]:
    global _wallet
    if _wallet is None and SODEX_PRIVATE_KEY:
        _wallet = Account.from_key(SODEX_PRIVATE_KEY)
    return _wallet


def is_configured() -> bool:
    return bool(SODEX_PRIVATE_KEY and SODEX_ADDRESS and SODEX_ACCOUNT_ID > 0)


def _next_nonce() -> int:
    global _nonce_counter
    now = int(time.time() * 1000)
    if now > _nonce_counter:
        _nonce_counter = now
    else:
        _nonce_counter += 1
    return _nonce_counter


def _keccak256(data: bytes) -> bytes:
    from Crypto.Hash import keccak
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


def _build_payload_hash(action_name: str, body: dict) -> bytes:
    """Compute keccak256(JSON({type: actionName, params: body})) matching Go struct field order."""
    envelope = {"type": action_name, "params": body}
    json_bytes = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _keccak256(json_bytes)


def _sign_action(payload_hash: bytes, nonce: int) -> str:
    """Sign an ExchangeAction and return the wire-format signature string."""
    wallet = _get_wallet()
    if wallet is None:
        raise RuntimeError("SODEX_PRIVATE_KEY not configured")

    msg = {
        "payloadHash": "0x" + payload_hash.hex(),
        "nonce": nonce,
    }

    signed = wallet.sign_typed_data(
        domain_data=_DOMAIN,
        types=_TYPES,
        primary_type="ExchangeAction",
        data=msg,
    )

    # Build wire format: 0x01 + r(32) + s(32) + v(0|1)
    r = signed.r.to_bytes(32, "big")
    s = signed.s.to_bytes(32, "big")
    v = signed.v - 27  # normalize 27/28 → 0/1
    wire = b"\x01" + r + s + bytes([v])
    return "0x" + wire.hex()


def _signed_headers(body: dict, scope: str, action_name: str) -> dict[str, str]:
    """Compute the EIP-712 signature and return auth headers."""
    payload_hash = _build_payload_hash(action_name, body)
    nonce = _next_nonce()
    sig = _sign_action(payload_hash, nonce)
    return {
        "X-API-Sign": sig,
        "X-API-Nonce": str(nonce),
        "X-API-Chain": str(SODEX_CHAIN_ID),
    }


# ---------------------------------------------------------------------------
# Read helpers (public, no auth)
# ---------------------------------------------------------------------------

async def get_spot_symbols() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SODEX_TIMEOUT_S) as client:
        resp = await client.get(f"{SODEX_BASE_URL}/spot/markets/symbols")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], list) else []
        return data if isinstance(data, list) else []


async def get_spot_symbol_by_id(symbol_id: int) -> Optional[dict[str, Any]]:
    symbols = await get_spot_symbols()
    for s in symbols:
        if s.get("id") == symbol_id:
            return s
    return None


async def find_symbol_for_asset(asset: str) -> Optional[dict[str, Any]]:
    """Find the best spot market for a plain asset name (e.g. 'BTC' → vBTC_vUSDC)."""
    symbols = await get_spot_symbols()
    needle = asset.upper()

    # Priority 1: baseCoin exact match
    for s in symbols:
        if str(s.get("baseCoin", "")).upper() == needle:
            return s

    # Priority 2: V-prefixed baseCoin
    for s in symbols:
        if str(s.get("baseCoin", "")).upper() == f"V{needle}":
            return s

    # Priority 3: name contains needle
    for s in symbols:
        name = str(s.get("name", "")).upper()
        if needle in name and "VUSDC" in name:
            return s

    return None


async def get_account_balances(address: str = None) -> list[dict[str, Any]]:
    addr = address or SODEX_ADDRESS
    async with httpx.AsyncClient(timeout=SODEX_TIMEOUT_S) as client:
        resp = await client.get(f"{SODEX_BASE_URL}/spot/accounts/{addr}/balances")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict):
                for key in ("balances", "list", "items"):
                    if key in inner and isinstance(inner[key], list):
                        return inner[key]
                return []
            return inner if isinstance(inner, list) else []
        return data if isinstance(data, list) else []


async def get_account_state(address: str = None) -> dict[str, Any]:
    addr = address or SODEX_ADDRESS
    async with httpx.AsyncClient(timeout=SODEX_TIMEOUT_S) as client:
        resp = await client.get(f"{SODEX_BASE_URL}/spot/accounts/{addr}/state")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], dict) else {}
        return data if isinstance(data, dict) else {}


async def get_spot_orderbook(symbol: str, depth: int = 10) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=SODEX_TIMEOUT_S) as client:
        resp = await client.get(
            f"{SODEX_BASE_URL}/spot/markets/{symbol}/orderbook",
            params={"limit": depth},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], dict) else {}
        return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Write helpers (authenticated, EIP-712 signed)
# ---------------------------------------------------------------------------

async def place_spot_order(
    symbol_id: int,
    side: int,
    price: str,
    quantity: str,
    time_in_force: int = 3,
    account_id: int = None,
    cl_ord_id: str = None,
) -> dict[str, Any]:
    """Place a single spot order on SoDEX.

    Args:
        symbol_id: SoDEX numeric symbol ID (e.g. 1 for vBTC_vUSDC)
        side: 1=buy, 2=sell
        price: limit price as string
        quantity: order quantity as string
        time_in_force: 1=IOC, 2=FOK, 3=GTC (default 3)
        account_id: SoDEX account ID (default from env)
        cl_ord_id: client order ID (auto-generated if None)
    """
    if not is_configured():
        return {"ok": False, "error": "SoDEX execution not configured (missing SODEX_PRIVATE_KEY / SODEX_ACCOUNT_ID)"}

    aid = account_id or SODEX_ACCOUNT_ID
    if cl_ord_id is None:
        cl_ord_id = f"sv-{int(time.time()*1000)}"

    order = {
        "symbolID": symbol_id,
        "clOrdID": cl_ord_id,
        "side": side,
        "type": 1,
        "timeInForce": time_in_force,
        "price": price,
        "quantity": quantity,
    }

    body = {"accountID": aid, "orders": [order]}
    headers = _signed_headers(body, "spot", "batchNewOrder")
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"

    async with httpx.AsyncClient(timeout=SODEX_TIMEOUT_S) as client:
        resp = await client.post(
            f"{SODEX_BASE_URL}/spot/trade/orders/batch",
            json=body,
            headers=headers,
        )
        result = resp.json()
        if resp.status_code >= 400 or (isinstance(result, dict) and result.get("code", 0) != 0):
            return {
                "ok": False,
                "status_code": resp.status_code,
                "error": result.get("error") or result.get("message") or str(result),
                "raw": result,
            }
        return {"ok": True, "data": result.get("data", result), "clOrdID": cl_ord_id}


async def place_basket_orders(
    allocations: list[dict[str, Any]],
    total_value_usdc: float,
    account_id: int = None,
) -> dict[str, Any]:
    """Execute a basket by placing spot orders for each non-stable leg.

    Maps SoSoValue index tickers to SoDEX proxy pairs:
      ssiMAG7, ssiLayer1 → vBTC_vUSDC
      ssiDeFi, ssiAI, etc → vETH_vUSDC
      USDC → skip (already stable)

    Returns summary with individual order results.
    """
    if not is_configured():
        return {
            "ok": False,
            "error": "SoDEX execution not configured",
            "mode": "unconfigured",
        }

    results: list[dict[str, Any]] = []
    total_allocated = 0.0

    for alloc in allocations:
        symbol = alloc.get("symbol", "")
        pct = alloc.get("percentage", 0)

        if symbol.upper() == "USDC" or alloc.get("type") == "Stable Reserve":
            results.append({
                "symbol": symbol,
                "action": "hold",
                "percentage": pct,
                "note": "Stable reserve — no trade needed",
            })
            continue

        # Map index ticker to SoDEX proxy pair
        proxy = await find_symbol_for_asset("BTC") if symbol.lower() in ("ssimag7", "ssilayer1") else await find_symbol_for_asset("ETH")
        if proxy is None:
            results.append({
                "symbol": symbol,
                "action": "failed",
                "error": f"No SoDEX proxy pair found for {symbol}",
            })
            continue

        notional = total_value_usdc * (pct / 100.0)
        total_allocated += notional

        if notional < 5.0:
            results.append({
                "symbol": symbol,
                "action": "skipped",
                "percentage": pct,
                "notional": round(notional, 2),
                "note": f"Below 5 USDC minimum (got {notional:.2f})",
            })
            continue

        # Get best ask price for a buy order
        orderbook = await get_spot_orderbook(proxy["name"], depth=5)
        asks = orderbook.get("asks") or orderbook.get("a") or []
        if not asks:
            results.append({
                "symbol": symbol,
                "action": "failed",
                "error": "No asks in orderbook",
                "proxy": proxy["name"],
            })
            continue

        best_ask = float(asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0].get("price", 0))
        if best_ask <= 0:
            results.append({
                "symbol": symbol,
                "action": "failed",
                "error": "Invalid ask price",
                "proxy": proxy["name"],
            })
            continue

        qty = round(notional / best_ask, proxy.get("quantityPrecision", 5))
        price_str = str(int(best_ask)) if proxy.get("pricePrecision", 0) == 0 else str(best_ask)
        qty_str = str(qty)

        order_result = await place_spot_order(
            symbol_id=proxy["id"],
            side=1,  # buy
            price=price_str,
            quantity=qty_str,
            account_id=account_id,
        )

        results.append({
            "symbol": symbol,
            "proxy_pair": proxy["name"],
            "action": "order_placed" if order_result.get("ok") else "order_failed",
            "percentage": pct,
            "notional": round(notional, 2),
            "quantity": qty_str,
            "price": price_str,
            "order": order_result,
        })

    return {
        "ok": all(r.get("action") in ("hold", "order_placed", "skipped") for r in results),
        "mode": "live-eip712",
        "account_id": account_id or SODEX_ACCOUNT_ID,
        "chain_id": SODEX_CHAIN_ID,
        "results": results,
        "total_value_usdc": round(total_value_usdc, 2),
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
