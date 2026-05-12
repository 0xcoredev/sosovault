"""
SoSoVault backend — agentic on-chain index portfolio API.

Wave 1 scope:
  - Live SoSoValue OpenAPI integration (indices, ETFs, news)
  - Groq LLM reasoning for basket explanations
  - SoDEX testnet read-only orderbook quotes
  - Mocked execution path (Wave 2 will sign real EIP-712 orders)

The smart contract (PortfolioManager.sol) ships compiled but is intentionally NOT
deployed for Wave 1. The hybrid paper-prototype scope was chosen to align with the
buildathon's official Wave 1 focus ("API usage plan, workflow design, early prototype")
and to defer contract deployment + signed order placement to Wave 2 ("initial SoDEX API
or execution module integration").
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import uuid
from enum import Enum
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from services import basket as basket_svc  # noqa: E402
from services import llm as llm_svc  # noqa: E402
from services import signals as signals_svc  # noqa: E402
from services import sodex as sodex_svc  # noqa: E402

app = FastAPI(
    title="SoSoVault API",
    description="Agentic on-chain index portfolios powered by SoSoValue + SoDEX.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Pydantic models                                                              #
# --------------------------------------------------------------------------- #

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyRequest(BaseModel):
    address: str
    riskLevel: RiskLevel
    currentPortfolio: Optional[dict[str, Any]] = None


class ExecuteRequest(BaseModel):
    address: str
    allocations: List[int]
    symbols: List[str]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _mock_tx_hash(seed: str) -> str:
    return "0x" + hashlib.sha256(f"{seed}-{uuid.uuid4()}".encode()).hexdigest()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Portfolio (Wave 1: deterministic fixture; Wave 2: read on-chain SoSoVault shares)
# --------------------------------------------------------------------------- #

def _portfolio_for(address: str) -> dict[str, Any]:
    """Deterministic fixture portfolio so the demo is reproducible per address."""
    random.seed(int(hashlib.sha256(address.encode()).hexdigest()[:8], 16))
    base = random.uniform(45000, 110000)
    change = round(random.uniform(-3.5, 6.5), 2)

    weights = [
        ("ssimag7", "SoSoValue Mag7 Index", "#627EEA", 0.42),
        ("ssilayer1", "SoSoValue Layer-1 Index", "#F7931A", 0.30),
        ("USDC", "USDC Reserve", "#2775CA", 0.28),
    ]
    tokens = []
    total = 0.0
    for sym, name, color, target in weights:
        value = round(base * target, 2)
        tokens.append(
            {
                "symbol": sym,
                "name": name,
                "balance": round(value if sym == "USDC" else value / 25.0, 4),
                "value": value,
                "percentage": round(target * 100, 1),
                "color": color,
            }
        )
        total += value
    # Snap percentages from real values to avoid rounding drift.
    for t in tokens:
        t["percentage"] = round((t["value"] / total) * 100, 1)
    return {
        "totalValue": round(total, 2),
        "change24h": change,
        "tokens": tokens,
    }


def _performance_for(address: str, period: str) -> list[dict[str, Any]]:
    random.seed(int(hashlib.sha256(f"perf-{address}-{period}".encode()).hexdigest()[:8], 16))
    days = {"24h": 1, "7d": 7, "30d": 30, "all": 90}.get(period, 30)
    base = random.uniform(70000, 95000)
    points: list[dict[str, Any]] = []
    for i in range(days):
        date = datetime.datetime.now() - datetime.timedelta(days=days - i)
        value = base + (i * random.uniform(-200, 350)) + random.uniform(-1500, 1800)
        points.append(
            {
                "date": date.strftime("%b %d"),
                "value": round(value, 2),
            }
        )
    return points


def _activity_for(address: str, limit: int) -> list[dict[str, Any]]:
    random.seed(int(hashlib.sha256(f"act-{address}".encode()).hexdigest()[:8], 16))
    types = ["deposit", "strategy", "rebalance", "rebalance", "strategy", "withdraw"]
    descriptions = {
        "deposit": [
            "Deposited 5,000 USDC",
            "Deposited 12,500 USDC",
            "Deposited 1,000 USDC",
        ],
        "strategy": [
            "Generated Medium-Risk basket from SoSoValue indices",
            "Generated High-Risk basket — Mag7 momentum tilt",
            "Generated Low-Risk basket — ETF flow risk-off",
        ],
        "rebalance": [
            "Auto-rebalance: +5% ssimag7 / -5% USDC (ETF inflow signal)",
            "Auto-rebalance: -3% ssilayer1 / +3% USDC (news risk-off)",
            "Auto-rebalance: +4% ssimag7 / -4% ssilayer1 (momentum gap)",
        ],
        "withdraw": [
            "Withdrew 2,000 USDC",
            "Withdrew 500 USDC",
        ],
    }
    base_time = datetime.datetime.now()
    items: list[dict[str, Any]] = []
    for i in range(min(limit, 12)):
        kind = random.choice(types)
        desc = random.choice(descriptions[kind])
        ts = base_time - datetime.timedelta(hours=i * random.randint(2, 14))
        items.append(
            {
                "id": i + 1,
                "type": kind,
                "description": desc,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                "status": "success" if random.random() > 0.1 else "pending",
                "txHash": _mock_tx_hash(f"{address}-{i}") if random.random() > 0.25 else None,
            }
        )
    return items


# --------------------------------------------------------------------------- #
# Routes                                                                      #
# --------------------------------------------------------------------------- #

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "SoSoVault API",
        "version": "0.1.0",
        "status": "ok",
        "wave": 1,
        "integrations": {
            "sosovalue_api": bool(os.getenv("SOSOVALUE_API_KEY")),
            "groq_llm": bool(os.getenv("GROQ_API_KEY")),
            "sodex_testnet": True,
            "smart_contract_deployed": False,
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": _now_iso()}


@app.get("/portfolio/{address}")
async def get_portfolio(address: str) -> dict[str, Any]:
    return _portfolio_for(address)


@app.get("/portfolio/{address}/performance")
async def get_performance(address: str, period: str = "30d") -> list[dict[str, Any]]:
    return _performance_for(address, period)


@app.get("/activity/{address}")
async def get_activity(address: str, limit: int = 50) -> list[dict[str, Any]]:
    return _activity_for(address, limit)


@app.post("/strategy/generate")
async def generate_strategy(request: StrategyRequest) -> dict[str, Any]:
    """Build a real basket from live SoSoValue data, with Groq-generated reasoning."""
    result = await basket_svc.build_basket(request.riskLevel.value)

    sosovalue_signals: dict[str, Any] = {
        "indices_used": result.indices_used,
        "sample_index_price": result.sample_index_price,
        "last_etf_inflow": result.last_etf_inflow,
        "allocations": result.allocations,
    }

    reasoning, llm_meta = llm_svc.generate_reasoning(
        risk_level=request.riskLevel.value,
        allocations=result.allocations,
        sosovalue_signals=sosovalue_signals,
    )
    if reasoning is None:
        reasoning = basket_svc.fallback_reasoning(request.riskLevel.value, result.allocations)

    return {
        "strategy": {
            "summary": result.summary,
            "constraints": result.constraints,
            "allocations": result.allocations,
            "reasoning": reasoning,
            "estimatedYield": result.estimated_yield,
            "estimatedGas": result.estimated_gas,
            "executionSteps": result.execution_steps,
        },
        "sosovalue": {
            "indices_used": result.indices_used,
            "sample_index_price": result.sample_index_price,
            "news_count": 0,  # populated separately on /signals/feed
            "last_etf_inflow": result.last_etf_inflow,
        },
        "llm": llm_meta,
    }


@app.post("/strategy/execute")
async def execute_strategy(request: ExecuteRequest) -> dict[str, Any]:
    """Wave 1 mocked execution.

    Wave 2 will:
      1. Quote the basket against SoDEX bookticker (already wired)
      2. Sign EIP-712 newOrder for each leg
      3. Submit via SoDEX REST `/api/v1/spot/orders`
      4. Persist tx and emit BasketRebalanced via deployed PortfolioManager
    """
    if len(request.allocations) != len(request.symbols):
        return {
            "ok": False,
            "error": "allocations and symbols length mismatch",
        }

    # Real SoDEX testnet read: try to fetch bookticker for any vBTC_vUSDC-style
    # symbols in the basket (USDC and SoSoValue index tickers won't have a SoDEX
    # pair; we attempt a best-effort fetch on BTC + ETH proxies).
    quote_symbols = []
    for sym in request.symbols:
        if sym.lower() in {"ssimag7", "ssilayer1", "btc"}:
            quote_symbols.append("vBTC_vUSDC")
        elif sym.lower() in {"ssidefi", "ssiai", "eth"}:
            quote_symbols.append("vETH_vUSDC")
    quote_symbols = list(dict.fromkeys(quote_symbols))  # dedupe, keep order
    sodex_route = await sodex_svc.quote_basket(quote_symbols) if quote_symbols else []

    return {
        "ok": True,
        "mode": "wave1-paper",
        "txHash": _mock_tx_hash(f"{request.address}-{json.dumps(request.allocations)}"),
        "submittedAt": _now_iso(),
        "weights": request.allocations,
        "symbols": request.symbols,
        "sodex_route": sodex_route,
        "note": (
            "Wave 1 ships a paper-execution path. Wave 2 will sign EIP-712 newOrder "
            "messages and submit them to the SoDEX testnet REST API."
        ),
    }


@app.get("/signals/feed")
async def signals_feed() -> dict[str, Any]:
    """Live ETF flow + index momentum + news sentiment signals."""
    return await signals_svc.build_signals_feed(news_limit=8)


@app.get("/sodex/quote")
async def sodex_quote(symbol: str) -> dict[str, Any]:
    """Live SoDEX testnet bookticker quote, e.g. ?symbol=vBTC_vUSDC."""
    quote = await sodex_svc.book_ticker(symbol)
    if quote is None:
        return {
            "symbol": symbol,
            "bidPx": "",
            "bidSz": "",
            "askPx": "",
            "askSz": "",
            "fetchedAt": _now_iso(),
            "stub": True,
        }
    return quote


if __name__ == "__main__":  # pragma: no cover - dev runner
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "3001")))
