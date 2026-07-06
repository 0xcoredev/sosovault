"""
SoSoVault backend — agentic on-chain index portfolio API.

Wave 2 scope:
  - Live SoSoValue OpenAPI integration (all 9 modules, 35+ endpoints)
  - EIP-712 SoDEX order execution (non-custodial, signed on backend)
  - SQLite persistence for signals, trades, agent logs, portfolio snapshots
  - Multi-agent pipeline: orchestrator → risk check → execution → tracking
  - Signal outcome tracking (HIT / STOP / DRIFT)
  - Background signal scanner (5-min generate, 2-min outcome scan)
  - Risk management: 4-check gatekeeper + circuit breaker
  - Groq LLM reasoning for basket explanations
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from services import basket as basket_svc  # noqa: E402
from services import database as db  # noqa: E402
from services import eip712  # noqa: E402
from services import llm as llm_svc  # noqa: E402
from services import orchestrator  # noqa: E402
from services import ratelimit  # noqa: E402
from services import risk as risk_svc  # noqa: E402
from services import scanner  # noqa: E402
from services import signals as signals_svc  # noqa: E402
from services import sodex as sodex_svc  # noqa: E402
from services import sosovalue  # noqa: E402


# --------------------------------------------------------------------------- #
# Lifespan — start background scanner on startup                              #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_db()
    scanner.start_background_scanner(interval_s=300)
    yield
    scanner.stop_background_scanner()


app = FastAPI(
    title="SoSoVault API",
    description="Agentic on-chain index portfolios powered by SoSoValue + SoDEX.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    ratelimit.RateLimitMiddleware,
    requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "60")),
    burst=int(os.getenv("RATE_LIMIT_BURST", "10")),
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
    totalValue: Optional[float] = None


class WalletConfigRequest(BaseModel):
    address: str
    label: Optional[str] = None
    riskLevel: str = "medium"
    autoRebalance: bool = False
    rebalanceThreshold: float = 0.7


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _mock_tx_hash(seed: str) -> str:
    return "0x" + hashlib.sha256(f"{seed}-{uuid.uuid4()}".encode()).hexdigest()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Root + Health                                                                #
# --------------------------------------------------------------------------- #

@app.get("/")
async def root() -> dict[str, Any]:
    stats = db.get_signal_stats()
    trade_stats = db.get_trade_stats()
    return {
        "service": "SoSoVault API",
        "version": "0.2.0",
        "status": "ok",
        "wave": 2,
        "integrations": {
            "sosovalue_api": bool(os.getenv("SOSOVALUE_API_KEY")),
            "groq_llm": bool(os.getenv("GROQ_API_KEY")),
            "sodex_testnet": True,
            "sodex_eip712": eip712.is_configured(),
            "smart_contract_deployed": bool(os.getenv("VITE_PORTFOLIO_MANAGER_ADDRESS")),
            "sqlite_db": True,
            "background_scanner": True,
        },
        "stats": {
            "signals": stats,
            "trades": trade_stats,
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": _now_iso()}


# --------------------------------------------------------------------------- #
# Portfolio (DB-backed snapshots + live SoDEX balances when EIP-712 configured)#
# --------------------------------------------------------------------------- #

@app.get("/portfolio/{address}")
async def get_portfolio(address: str) -> dict[str, Any]:
    # Try to get real SoDEX balances if configured
    if eip712.is_configured():
        try:
            balances = await eip712.get_account_balances(address)
            if balances:
                total = 0.0
                tokens = []
                for b in balances:
                    coin = b.get("coin", b.get("asset", ""))
                    available = float(b.get("available", b.get("free", 0)))
                    if available <= 0:
                        continue
                    tokens.append({
                        "symbol": coin,
                        "name": coin,
                        "balance": available,
                        "value": available,  # approximate — USDC ≈ $1
                        "percentage": 0,
                        "color": "#2775CA" if "USDC" in coin.upper() else "#627EEA",
                    })
                    total += available
                if total > 0:
                    for t in tokens:
                        t["percentage"] = round((t["value"] / total) * 100, 1)
                    return {"totalValue": round(total, 2), "change24h": 0.0, "tokens": tokens}
        except Exception:
            pass

    # Fall back to latest DB snapshot
    snapshots = db.get_snapshots(address, limit=1)
    if snapshots:
        snap = snapshots[0]
        return {
            "totalValue": snap["total_value"],
            "change24h": 0.0,
            "tokens": snap["allocations"],
        }

    # Final fallback: deterministic fixture
    return _portfolio_for(address)


def _portfolio_for(address: str) -> dict[str, Any]:
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
        tokens.append({
            "symbol": sym, "name": name,
            "balance": round(value if sym == "USDC" else value / 25.0, 4),
            "value": value, "percentage": round(target * 100, 1), "color": color,
        })
        total += value
    for t in tokens:
        t["percentage"] = round((t["value"] / total) * 100, 1)
    return {"totalValue": round(total, 2), "change24h": change, "tokens": tokens}


@app.get("/portfolio/{address}/performance")
async def get_performance(address: str, period: str = "30d") -> list[dict[str, Any]]:
    snapshots = db.get_snapshots(address, limit=90)
    if len(snapshots) >= 3:
        points = []
        for snap in reversed(snapshots):
            points.append({
                "date": snap["created_at"][:10],
                "value": snap["total_value"],
            })
        return points

    # Fallback: deterministic fixture
    random.seed(int(hashlib.sha256(f"perf-{address}-{period}".encode()).hexdigest()[:8], 16))
    days = {"24h": 1, "7d": 7, "30d": 30, "all": 90}.get(period, 30)
    base = random.uniform(70000, 95000)
    points = []
    for i in range(days):
        date = datetime.datetime.now() - datetime.timedelta(days=days - i)
        value = base + (i * random.uniform(-200, 350)) + random.uniform(-1500, 1800)
        points.append({"date": date.strftime("%b %d"), "value": round(value, 2)})
    return points


@app.get("/activity/{address}")
async def get_activity(address: str, limit: int = 50) -> list[dict[str, Any]]:
    trades = db.get_trades(address=address, limit=limit)
    if trades:
        items = []
        for t in trades:
            items.append({
                "id": t["id"],
                "type": "rebalance" if t["side"] == "buy" else "withdraw",
                "description": f"{t['side'].upper()} {t['quantity']} {t['symbol']} @ {t['price']}",
                "timestamp": t["created_at"][:16],
                "status": t["status"].lower(),
                "txHash": t.get("tx_hash") or t.get("sodex_order_id"),
            })
        return items

    # Fallback: deterministic fixture
    random.seed(int(hashlib.sha256(f"act-{address}".encode()).hexdigest()[:8], 16))
    types = ["deposit", "strategy", "rebalance", "rebalance", "strategy", "withdraw"]
    descriptions = {
        "deposit": ["Deposited 5,000 USDC", "Deposited 12,500 USDC", "Deposited 1,000 USDC"],
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
        "withdraw": ["Withdrew 2,000 USDC", "Withdrew 500 USDC"],
    }
    base_time = datetime.datetime.now()
    items = []
    for i in range(min(limit, 12)):
        kind = random.choice(types)
        desc = random.choice(descriptions[kind])
        ts = base_time - datetime.timedelta(hours=i * random.randint(2, 14))
        items.append({
            "id": i + 1, "type": kind, "description": desc,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
            "status": "success" if random.random() > 0.1 else "pending",
            "txHash": _mock_tx_hash(f"{address}-{i}") if random.random() > 0.25 else None,
        })
    return items


# --------------------------------------------------------------------------- #
# Strategy — agent orchestrator pipeline                                       #
# --------------------------------------------------------------------------- #

@app.post("/strategy/generate")
async def generate_strategy(request: StrategyRequest) -> dict[str, Any]:
    """Build a live basket with full agent pipeline: SoSoValue → AI reasoning → risk check."""
    return await orchestrator.generate_strategy(request.riskLevel.value, request.address)


@app.post("/strategy/execute")
async def execute_strategy(request: ExecuteRequest) -> dict[str, Any]:
    """Execute a basket — EIP-712 signed orders on SoDEX if configured, else paper quotes."""
    if len(request.allocations) != len(request.symbols):
        return {"ok": False, "error": "allocations and symbols length mismatch"}

    allocations = [
        {"symbol": sym, "percentage": pct, "type": "Index" if sym.upper() != "USDC" else "Stable Reserve"}
        for sym, pct in zip(request.symbols, request.allocations)
    ]

    total_value = request.totalValue or 10000.0

    return await orchestrator.execute_basket(
        address=request.address,
        allocations=allocations,
        total_value_usdc=total_value,
    )


# --------------------------------------------------------------------------- #
# Signals — live feed + outcome tracking                                       #
# --------------------------------------------------------------------------- #

@app.get("/signals/feed")
async def signals_feed() -> dict[str, Any]:
    """Live ETF flow + index momentum + news sentiment signals."""
    return await signals_svc.build_signals_feed(news_limit=8)


@app.get("/signals/tracker")
async def signals_tracker(limit: int = 50) -> dict[str, Any]:
    """Signal outcome tracker — shows HIT/STOP/DRIFT/PENDING for all signals."""
    signals = db.get_signals_with_outcomes(limit=limit)
    stats = db.get_signal_stats()
    return {"signals": signals, "stats": stats}


@app.get("/signals/stats")
async def signals_stats() -> dict[str, Any]:
    """Public signal accuracy statistics."""
    return db.get_signal_stats()


@app.post("/signals/scan")
async def trigger_signal_scan() -> dict[str, Any]:
    """Manually trigger a signal scan + generation cycle."""
    gen_result = await scanner.generate_and_store_signals()
    scan_result = await scanner.scan_pending_signals()
    return {"generated": gen_result, "scanned": scan_result}


# --------------------------------------------------------------------------- #
# Trades                                                                       #
# --------------------------------------------------------------------------- #

@app.get("/trades")
async def get_trades(address: str = None, limit: int = 50) -> dict[str, Any]:
    """Get trade history, optionally filtered by address."""
    trades = db.get_trades(address=address, limit=limit)
    stats = db.get_trade_stats()
    return {"trades": trades, "stats": stats}


@app.get("/trades/stats")
async def trade_stats() -> dict[str, Any]:
    return db.get_trade_stats()


# --------------------------------------------------------------------------- #
# Agent Logs                                                                   #
# --------------------------------------------------------------------------- #

@app.get("/agent/logs")
async def agent_logs(agent: str = None, limit: int = 50) -> list[dict[str, Any]]:
    return db.get_agent_logs(agent=agent, limit=limit)


# --------------------------------------------------------------------------- #
# Risk Management                                                              #
# --------------------------------------------------------------------------- #

@app.get("/risk/status")
async def risk_status() -> dict[str, Any]:
    return risk_svc.get_risk_status()


@app.post("/risk/check")
async def risk_check(address: str, confidence: float = 0.7) -> dict[str, Any]:
    return risk_svc.run_all_checks(address=address, confidence=confidence)


@app.post("/risk/circuit-breaker/reset")
async def reset_circuit_breaker() -> dict[str, Any]:
    return risk_svc.reset_circuit_breaker()


# --------------------------------------------------------------------------- #
# SoDEX — read-only + execution                                                #
# --------------------------------------------------------------------------- #

@app.get("/sodex/quote")
async def sodex_quote(symbol: str) -> dict[str, Any]:
    """Live SoDEX testnet bookticker quote."""
    quote = await sodex_svc.book_ticker(symbol)
    if quote is None:
        return {
            "symbol": symbol, "bidPx": "", "bidSz": "", "askPx": "", "askSz": "",
            "fetchedAt": _now_iso(), "stub": True,
        }
    return quote


@app.get("/sodex/symbols")
async def sodex_symbols() -> list[dict[str, Any]]:
    """List all SoDEX spot markets."""
    return await eip712.get_spot_symbols()


@app.get("/sodex/orderbook")
async def sodex_orderbook(symbol: str, depth: int = 10) -> dict[str, Any]:
    """Get SoDEX orderbook for a symbol."""
    return await eip712.get_spot_orderbook(symbol, depth)


@app.get("/sodex/balances/{address}")
async def sodex_balances(address: str) -> list[dict[str, Any]]:
    """Get SoDEX account balances for an address."""
    return await eip712.get_account_balances(address)


@app.get("/sodex/status")
async def sodex_status() -> dict[str, Any]:
    """SoDEX integration status."""
    return {
        "configured": eip712.is_configured(),
        "chain_id": eip712.SODEX_CHAIN_ID,
        "base_url": eip712.SODEX_BASE_URL,
        "address": eip712.SODEX_ADDRESS[:10] + "..." if eip712.SODEX_ADDRESS else "",
        "account_id": eip712.SODEX_ACCOUNT_ID,
    }


# --------------------------------------------------------------------------- #
# Wallet Configuration                                                         #
# --------------------------------------------------------------------------- #

@app.post("/wallet/config")
async def configure_wallet(req: WalletConfigRequest) -> dict[str, Any]:
    """Save wallet preferences (risk level, auto-rebalance)."""
    db.upsert_wallet(
        address=req.address,
        label=req.label,
        risk_level=req.riskLevel,
        auto_rebalance=req.autoRebalance,
        rebalance_threshold=req.rebalanceThreshold,
    )
    return {"ok": True, "address": req.address}


@app.get("/wallet/{address}")
async def get_wallet_config(address: str) -> dict[str, Any]:
    wallet = db.get_wallet(address)
    if wallet is None:
        return {"address": address, "risk_level": "medium", "auto_rebalance": False}
    return wallet


# --------------------------------------------------------------------------- #
# SoSoValue Extended Data                                                      #
# --------------------------------------------------------------------------- #

@app.get("/sosovalue/indices")
async def sosovalue_indices() -> list[str]:
    return await sosovalue.list_indices()


@app.get("/sosovalue/indices/{ticker}/snapshot")
async def sosovalue_index_snapshot(ticker: str) -> dict[str, Any]:
    snap = await sosovalue.index_snapshot(ticker)
    return snap or {"error": "unavailable", "ticker": ticker}


@app.get("/sosovalue/indices/{ticker}/constituents")
async def sosovalue_index_constituents(ticker: str) -> list[dict[str, Any]]:
    return await sosovalue.index_constituents(ticker)


@app.get("/sosovalue/etfs")
async def sosovalue_etfs() -> list[dict[str, Any]]:
    return await sosovalue.list_etfs()


@app.get("/sosovalue/etfs/{ticker}/snapshot")
async def sosovalue_etf_snapshot(ticker: str) -> dict[str, Any]:
    snap = await sosovalue.etf_snapshot(ticker)
    return snap or {"error": "unavailable", "ticker": ticker}


@app.get("/sosovalue/news")
async def sosovalue_news(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return await sosovalue.news(page=page, page_size=page_size)


@app.get("/sosovalue/currencies")
async def sosovalue_currencies() -> list[dict[str, Any]]:
    return await sosovalue.list_currencies()


@app.get("/sosovalue/currencies/{currency_id}/snapshot")
async def sosovalue_currency_snapshot(currency_id: str) -> dict[str, Any]:
    snap = await sosovalue.currency_snapshot(currency_id)
    return snap or {"error": "unavailable"}


@app.get("/sosovalue/crypto-stocks")
async def sosovalue_crypto_stocks() -> list[dict[str, Any]]:
    return await sosovalue.list_crypto_stocks()


@app.get("/sosovalue/crypto-stocks/{ticker}/snapshot")
async def sosovalue_stock_snapshot(ticker: str) -> dict[str, Any]:
    snap = await sosovalue.crypto_stock_snapshot(ticker)
    return snap or {"error": "unavailable"}


@app.get("/sosovalue/crypto-stocks/sectors")
async def sosovalue_stock_sectors() -> Any:
    return await sosovalue.crypto_stock_sectors()


@app.get("/sosovalue/btc-treasuries")
async def sosovalue_btc_treasuries() -> list[dict[str, Any]]:
    return await sosovalue.btc_treasuries()


@app.get("/sosovalue/btc-treasuries/{ticker}/history")
async def sosovalue_btc_purchase_history(ticker: str) -> Any:
    return await sosovalue.btc_purchase_history(ticker)


@app.get("/sosovalue/fundraising")
async def sosovalue_fundraising(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return await sosovalue.fundraising_projects(page=page, page_size=page_size)


@app.get("/sosovalue/fundraising/{project_id}")
async def sosovalue_fundraising_detail(project_id: str) -> dict[str, Any]:
    detail = await sosovalue.fundraising_project_detail(project_id)
    return detail or {"error": "unavailable"}


@app.get("/sosovalue/macro/events")
async def sosovalue_macro_events(date: str = None) -> Any:
    return await sosovalue.macro_events(date)


@app.get("/sosovalue/macro/events/{event}/history")
async def sosovalue_macro_event_history(event: str) -> Any:
    return await sosovalue.macro_event_history(event)


@app.get("/sosovalue/analyses")
async def sosovalue_analyses() -> list[dict[str, Any]]:
    return await sosovalue.analysis_charts()


@app.get("/sosovalue/analyses/{chart_name}")
async def sosovalue_analysis_data(chart_name: str) -> Any:
    return await sosovalue.analysis_chart_data(chart_name)


@app.get("/sosovalue/sector-spotlight")
async def sosovalue_sector_spotlight() -> Any:
    return await sosovalue.sector_spotlight()


# --------------------------------------------------------------------------- #
# Sectors Intelligence                                                         #
# --------------------------------------------------------------------------- #

@app.get("/sectors/intel")
async def sectors_intelligence() -> dict[str, Any]:
    """Score all available SoSoValue indices as sector intelligence."""
    indices = await sosovalue.list_indices()
    sectors = []
    for ticker in indices:
        snap = await sosovalue.index_snapshot(ticker)
        if not snap:
            continue
        try:
            roi_1m = float(snap.get("roi_1m") or snap.get("1month_roi") or 0)
            roi_7d = float(snap.get("roi_7d") or snap.get("7day_roi") or 0)
            roi_1y = float(snap.get("roi_1y") or snap.get("1year_roi") or 0)
            change_24h = float(snap.get("change_pct_24h") or snap.get("24h_change_pct") or 0)
            price = float(snap.get("price") or 0)
        except (TypeError, ValueError):
            roi_1m = roi_7d = roi_1y = change_24h = price = 0.0

        # Composite score: 30% 7d ROI + 35% 1m ROI + 35% momentum
        s1 = max(0, min(100, 50 + roi_7d * 500))
        s2 = max(0, min(100, 50 + roi_1m * 200))
        s3 = max(0, min(100, 50 + change_24h * 20))
        score = round(s1 * 0.30 + s2 * 0.35 + s3 * 0.35, 1)

        if score >= 75:
            verdict = "STRONG_BUY"
        elif score >= 55:
            verdict = "BUY"
        elif score >= 35:
            verdict = "NEUTRAL"
        else:
            verdict = "SELL"

        sectors.append({
            "ticker": ticker,
            "price": price,
            "change_24h": round(change_24h * 100, 2),
            "roi_7d": round(roi_7d * 100, 2),
            "roi_1m": round(roi_1m * 100, 2),
            "roi_1y": round(roi_1y * 100, 2),
            "score": score,
            "verdict": verdict,
        })

    sectors.sort(key=lambda s: s["score"], reverse=True)
    return {"sectors": sectors, "count": len(sectors), "generated_at": _now_iso()}


@app.get("/sectors/intel/{ticker}/basket")
async def sector_basket(ticker: str) -> dict[str, Any]:
    """Get top 3 assets for a sector index."""
    constituents = await sosovalue.index_constituents(ticker)
    if not constituents:
        return {"ticker": ticker, "assets": [], "error": "unavailable"}
    top3 = constituents[:3]
    return {"ticker": ticker, "assets": top3}


# --------------------------------------------------------------------------- #
# Portfolio Snapshots                                                          #
# --------------------------------------------------------------------------- #

@app.get("/snapshots/{address}")
async def get_snapshots(address: str, limit: int = 30) -> list[dict[str, Any]]:
    return db.get_snapshots(address, limit=limit)


if __name__ == "__main__":  # pragma: no cover - dev runner
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "3001")))
