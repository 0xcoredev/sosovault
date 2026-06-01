"""
Agent orchestrator for SoSoVault (Wave 2).

Coordinates the signal → risk check → execution → tracking pipeline.

Flow:
  1. Generate signals from live SoSoValue data
  2. Run risk checks against the proposed basket
  3. If risk passes, execute via EIP-712 SoDEX orders
  4. Record the trade in SQLite
  5. Log all agent actions
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from . import basket as basket_svc
from . import database as db
from . import eip712
from . import llm as llm_svc
from . import risk as risk_svc
from . import sodex as sodex_svc


async def generate_strategy(risk_level: str, address: str) -> dict[str, Any]:
    """Generate a basket strategy with full agent pipeline."""
    t0 = time.time()

    # 1. Build basket from live SoSoValue data
    result = await basket_svc.build_basket(risk_level)
    basket_ms = int((time.time() - t0) * 1000)

    # 2. Generate AI reasoning
    sosovalue_signals = {
        "indices_used": result.indices_used,
        "sample_index_price": result.sample_index_price,
        "last_etf_inflow": result.last_etf_inflow,
        "allocations": result.allocations,
    }
    reasoning, llm_meta = llm_svc.generate_reasoning(
        risk_level=risk_level,
        allocations=result.allocations,
        sosovalue_signals=sosovalue_signals,
    )
    if reasoning is None:
        reasoning = basket_svc.fallback_reasoning(risk_level, result.allocations)

    # 3. Run risk checks
    risk_result = risk_svc.run_all_checks(
        address=address,
        allocations=result.allocations,
        confidence=0.7,
    )

    total_ms = int((time.time() - t0) * 1000)
    db.log_agent_action(
        agent="orchestrator",
        action="generate_strategy",
        input_data={"risk_level": risk_level, "address": address},
        output_data={
            "basket_ms": basket_ms,
            "total_ms": total_ms,
            "risk_passed": risk_result["all_passed"],
            "indices_used": result.indices_used,
        },
        success=True,
        latency_ms=total_ms,
    )

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
            "last_etf_inflow": result.last_etf_inflow,
        },
        "llm": llm_meta,
        "risk": risk_result,
    }


async def execute_basket(
    address: str,
    allocations: list[dict[str, Any]],
    total_value_usdc: float,
    signal_id: str = None,
) -> dict[str, Any]:
    """Execute a basket through the full agent pipeline.

    1. Risk check
    2. EIP-712 order placement
    3. Trade recording
    4. Agent logging
    """
    t0 = time.time()

    # 1. Risk check
    risk_result = risk_svc.run_all_checks(
        address=address,
        allocations=allocations,
        confidence=0.7,
    )

    if not risk_result["all_passed"]:
        failed_checks = [c for c in risk_result["checks"] if not c.get("passed")]
        db.log_agent_action(
            agent="orchestrator",
            action="execute_rejected",
            input_data={"address": address, "allocations": allocations},
            output_data={"reason": "risk_check_failed", "failed_checks": failed_checks},
            success=False,
            latency_ms=int((time.time() - t0) * 1000),
        )
        return {
            "ok": False,
            "mode": "risk-rejected",
            "reason": "Risk management rejected this execution",
            "risk": risk_result,
            "failed_checks": failed_checks,
        }

    # 2. Execute via EIP-712
    if eip712.is_configured():
        execution_result = await eip712.place_basket_orders(
            allocations=allocations,
            total_value_usdc=total_value_usdc,
        )
        mode = "live-eip712"
    else:
        # Fallback to read-only SoDEX quotes
        quote_symbols = []
        for alloc in allocations:
            sym = alloc.get("symbol", "").lower()
            if sym in ("ssimag7", "ssilayer1", "btc"):
                quote_symbols.append("vBTC_vUSDC")
            elif sym in ("ssidefi", "ssiai", "eth"):
                quote_symbols.append("vETH_vUSDC")
        quote_symbols = list(dict.fromkeys(quote_symbols))
        sodex_route = await sodex_svc.quote_basket(quote_symbols) if quote_symbols else []
        execution_result = {
            "ok": True,
            "mode": "paper-quotes",
            "results": [{"symbol": a["symbol"], "action": "paper", "percentage": a["percentage"]} for a in allocations],
            "sodex_route": sodex_route,
        }
        mode = "paper-quotes"

    # 3. Record trades in DB
    for result_item in execution_result.get("results", []):
        if result_item.get("action") == "order_placed":
            order = result_item.get("order", {})
            db.insert_trade({
                "address": address,
                "signal_id": signal_id,
                "symbol": result_item.get("proxy_pair", result_item.get("symbol", "")),
                "side": "buy",
                "order_type": "LIMIT_IOC",
                "quantity": float(result_item.get("quantity", 0)),
                "price": float(result_item.get("price", 0)),
                "notional": result_item.get("notional", 0),
                "sodex_order_id": order.get("data", {}).get("orderID") if isinstance(order.get("data"), dict) else None,
                "status": "FILLED" if order.get("ok") else "FAILED",
                "error_message": order.get("error") if not order.get("ok") else None,
            })

    # 4. Record portfolio snapshot
    db.insert_snapshot(address, total_value_usdc, allocations)

    if execution_result.get("ok"):
        risk_svc.record_trade_success()
    else:
        risk_svc.record_trade_failure()

    total_ms = int((time.time() - t0) * 1000)
    db.log_agent_action(
        agent="orchestrator",
        action="execute_basket",
        input_data={"address": address, "total_value": total_value_usdc},
        output_data={"mode": mode, "ok": execution_result.get("ok")},
        success=execution_result.get("ok", False),
        latency_ms=total_ms,
    )

    return {
        **execution_result,
        "risk": risk_result,
        "latency_ms": total_ms,
    }
