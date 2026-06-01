"""
Risk management agent for SoSoVault (Wave 2).

Implements a 4-check gatekeeper before any trade execution:
  1. Daily trade cap — max 10 trades per 24h
  2. Portfolio concentration — max 40% in any single asset
  3. Signal confidence floor — minimum 0.55 confidence
  4. Daily drawdown halt — pause if portfolio drops >5% in 24h

Also implements a circuit breaker:
  - 3 consecutive trade failures → 1h pause
  - Per-asset: >3 losses in 24h → block that asset for 24h
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from . import database as db

# Risk parameters
MAX_DAILY_TRADES = 10
MAX_CONCENTRATION_PCT = 40.0
MIN_SIGNAL_CONFIDENCE = 0.55
MAX_DAILY_DRAWDOWN_PCT = 5.0
CIRCUIT_BREAKER_CONSECUTIVE_FAILS = 3
CIRCUIT_BREAKER_COOLDOWN_S = 3600  # 1 hour

# State
_circuit_open_until: float = 0.0
_consecutive_fails: int = 0
_asset_failures: dict[str, list[float]] = {}


def _now() -> float:
    return time.time()


def _today_start() -> float:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def check_daily_trade_cap(address: str) -> dict[str, Any]:
    """Check if the address has exceeded the daily trade limit."""
    trades = db.get_trades(address=address, limit=100)
    today_start = _today_start()
    today_trades = [
        t for t in trades
        if t.get("created_at", "") >= datetime.fromtimestamp(today_start, timezone.utc).isoformat()
    ]
    count = len(today_trades)
    return {
        "check": "daily_trade_cap",
        "passed": count < MAX_DAILY_TRADES,
        "current": count,
        "limit": MAX_DAILY_TRADES,
        "remaining": max(0, MAX_DAILY_TRADES - count),
    }


def check_concentration(allocations: list[dict[str, Any]]) -> dict[str, Any]:
    """Check if any single allocation exceeds the concentration limit."""
    violations = []
    for alloc in allocations:
        pct = alloc.get("percentage", 0)
        if pct > MAX_CONCENTRATION_PCT:
            violations.append({
                "symbol": alloc.get("symbol"),
                "percentage": pct,
                "limit": MAX_CONCENTRATION_PCT,
            })
    return {
        "check": "concentration",
        "passed": len(violations) == 0,
        "violations": violations,
    }


def check_signal_confidence(confidence: float) -> dict[str, Any]:
    """Check if signal confidence meets the minimum threshold."""
    return {
        "check": "signal_confidence",
        "passed": confidence >= MIN_SIGNAL_CONFIDENCE,
        "confidence": confidence,
        "minimum": MIN_SIGNAL_CONFIDENCE,
    }


def check_drawdown(portfolio_value: float, yesterday_value: float) -> dict[str, Any]:
    """Check if daily drawdown exceeds the halt threshold."""
    if yesterday_value <= 0:
        return {"check": "drawdown", "passed": True, "drawdown_pct": 0.0}
    drawdown_pct = ((yesterday_value - portfolio_value) / yesterday_value) * 100
    return {
        "check": "drawdown",
        "passed": drawdown_pct < MAX_DAILY_DRAWDOWN_PCT,
        "drawdown_pct": round(drawdown_pct, 2),
        "threshold": MAX_DAILY_DRAWDOWN_PCT,
    }


def check_circuit_breaker() -> dict[str, Any]:
    """Check if the circuit breaker is tripped."""
    global _circuit_open_until
    if _now() < _circuit_open_until:
        remaining = int(_circuit_open_until - _now())
        return {
            "check": "circuit_breaker",
            "passed": False,
            "reason": f"Circuit breaker open — {remaining}s cooldown remaining",
            "cooldown_remaining_s": remaining,
        }
    return {
        "check": "circuit_breaker",
        "passed": True,
        "consecutive_fails": _consecutive_fails,
    }


def record_trade_failure() -> None:
    """Record a trade failure for circuit breaker tracking."""
    global _consecutive_fails, _circuit_open_until
    _consecutive_fails += 1
    if _consecutive_fails >= CIRCUIT_BREAKER_CONSECUTIVE_FAILS:
        _circuit_open_until = _now() + CIRCUIT_BREAKER_COOLDOWN_S
        print(f"[risk] Circuit breaker tripped after {_consecutive_fails} consecutive failures. "
              f"Cooldown: {CIRCUIT_BREAKER_COOLDOWN_S}s")
        db.log_agent_action(
            agent="risk_manager",
            action="circuit_breaker_tripped",
            output_data={"consecutive_fails": _consecutive_fails, "cooldown_s": CIRCUIT_BREAKER_COOLDOWN_S},
            success=False,
        )


def record_trade_success() -> None:
    """Reset consecutive failure counter on successful trade."""
    global _consecutive_fails
    _consecutive_fails = 0


def record_asset_failure(asset: str) -> None:
    """Track per-asset failures. Block asset if >3 failures in 24h."""
    now = _now()
    if asset not in _asset_failures:
        _asset_failures[asset] = []
    _asset_failures[asset].append(now)
    # Prune entries older than 24h
    _asset_failures[asset] = [t for t in _asset_failures[asset] if now - t < 86400]


def is_asset_blocked(asset: str) -> bool:
    """Check if an asset is blocked due to repeated failures."""
    failures = _asset_failures.get(asset, [])
    now = _now()
    recent = [t for t in failures if now - t < 86400]
    return len(recent) > 3


def run_all_checks(
    address: str,
    allocations: list[dict[str, Any]] = None,
    confidence: float = 0.7,
    portfolio_value: float = 0.0,
    yesterday_value: float = 0.0,
) -> dict[str, Any]:
    """Run all risk checks and return a comprehensive report."""
    checks = []

    # 1. Circuit breaker
    cb = check_circuit_breaker()
    checks.append(cb)

    # 2. Daily trade cap
    dt = check_daily_trade_cap(address)
    checks.append(dt)

    # 3. Concentration
    if allocations:
        cc = check_concentration(allocations)
        checks.append(cc)

    # 4. Signal confidence
    sc = check_signal_confidence(confidence)
    checks.append(sc)

    # 5. Drawdown
    if portfolio_value > 0 and yesterday_value > 0:
        dd = check_drawdown(portfolio_value, yesterday_value)
        checks.append(dd)

    all_passed = all(c.get("passed", False) for c in checks)

    result = {
        "all_passed": all_passed,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    db.log_agent_action(
        agent="risk_manager",
        action="run_checks",
        input_data={"address": address, "confidence": confidence},
        output_data=result,
        success=all_passed,
    )

    return result


def get_risk_status() -> dict[str, Any]:
    """Get current risk management status for the dashboard."""
    return {
        "circuit_breaker": {
            "open": _now() < _circuit_open_until,
            "consecutive_fails": _consecutive_fails,
            "cooldown_remaining_s": max(0, int(_circuit_open_until - _now())),
        },
        "parameters": {
            "max_daily_trades": MAX_DAILY_TRADES,
            "max_concentration_pct": MAX_CONCENTRATION_PCT,
            "min_signal_confidence": MIN_SIGNAL_CONFIDENCE,
            "max_daily_drawdown_pct": MAX_DAILY_DRAWDOWN_PCT,
        },
        "blocked_assets": [a for a in _asset_failures if is_asset_blocked(a)],
    }


def reset_circuit_breaker() -> dict[str, Any]:
    """Manual circuit breaker reset."""
    global _circuit_open_until, _consecutive_fails
    _circuit_open_until = 0.0
    _consecutive_fails = 0
    db.log_agent_action(
        agent="risk_manager",
        action="circuit_breaker_reset",
        output_data={"manual": True},
        success=True,
    )
    return {"ok": True, "message": "Circuit breaker reset"}
