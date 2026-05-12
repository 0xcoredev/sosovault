"""
Core basket builder.

Given a risk tier and live SoSoValue data, produce a target basket:
weights, expected yield, constraints, execution steps. The reasoning prose
is generated separately by `services.llm`.

The builder:

1. Pulls the SoSoValue index list (`/indices`) and selects up to 2 indices to use.
2. Fetches each index's market snapshot (`/indices/{ticker}/market-snapshot`) for
   the live 1-month and 1-year ROI plus 24h change.
3. Pulls the latest ETF snapshot for IBIT (BTC spot ETF) as the ETF flow signal.
4. Allocates weights based on the risk tier and a momentum tilt:
     - Higher 1-month ROI -> larger share of the volatile sleeve
     - Negative ETF flow tilts the basket toward the stable reserve
5. Returns a structured `BasketResult` ready to be JSON-serialised.

If SoSoValue is unreachable, it falls back to deterministic templated weights so
the demo never breaks.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from . import sosovalue

# Default index candidates. The builder will only use ones that are actually present
# in the live `/indices` response, so this stays robust if SoSoValue renames anything.
PREFERRED_INDICES = ("ssimag7", "ssilayer1", "ssidefi", "ssiai", "ssimeme")

# Risk-tier base weights (stable, primary_index, secondary_index).
RISK_BASE_WEIGHTS: dict[str, tuple[int, int, int]] = {
    "low": (50, 35, 15),
    "medium": (30, 40, 30),
    "high": (15, 60, 25),
}

# Display colours per symbol - keep consistent with frontend mock-data.
SYMBOL_COLORS: dict[str, str] = {
    "USDC": "#2775CA",
    "ssimag7": "#627EEA",
    "ssilayer1": "#F7931A",
    "ssidefi": "#B6509E",
    "ssiai": "#10B981",
    "ssimeme": "#F59E0B",
}

INDEX_DISPLAY: dict[str, str] = {
    "ssimag7": "SoSoValue Mag7 Index",
    "ssilayer1": "SoSoValue Layer-1 Index",
    "ssidefi": "SoSoValue DeFi Index",
    "ssiai": "SoSoValue AI Index",
    "ssimeme": "SoSoValue Meme Index",
}


@dataclass
class BasketResult:
    summary: str
    constraints: list[str]
    allocations: list[dict[str, Any]]  # {symbol, name, percentage, type, oneMonthRoi, oneYearRoi, color}
    estimated_yield: float
    estimated_gas: float
    execution_steps: list[str]
    indices_used: list[str] = field(default_factory=list)
    sample_index_price: float | None = None
    last_etf_inflow: float | None = None


def _normalise_to_100(values: list[int]) -> list[int]:
    """Renormalise a list of int weights so they sum to 100 without overflowing."""
    total = sum(values) or 1
    scaled = [round(v * 100 / total) for v in values]
    drift = 100 - sum(scaled)
    if scaled:
        scaled[0] = max(0, scaled[0] + drift)
    return scaled


async def _pick_indices(available: list[str]) -> list[str]:
    """Return up to two index tickers, preferring our known set, falling back to live order."""
    by_priority = [t for t in PREFERRED_INDICES if t in available]
    if len(by_priority) >= 2:
        return by_priority[:2]
    extras = [t for t in available if t not in by_priority]
    return (by_priority + extras)[:2] or ["ssimag7", "ssilayer1"]


async def build_basket(risk_level: str) -> BasketResult:
    """Build a live basket for the given risk tier."""
    risk_level = (risk_level or "medium").lower()
    if risk_level not in RISK_BASE_WEIGHTS:
        risk_level = "medium"

    # Fetch SoSoValue inputs in parallel.
    indices_task = asyncio.create_task(sosovalue.list_indices())
    etf_task = asyncio.create_task(sosovalue.etf_snapshot("IBIT"))
    available_indices, etf = await asyncio.gather(indices_task, etf_task)

    chosen = await _pick_indices(available_indices)
    primary, secondary = chosen[0], chosen[1] if len(chosen) > 1 else chosen[0]

    snap_primary = await sosovalue.index_snapshot(primary)
    snap_secondary = await sosovalue.index_snapshot(secondary)

    # Risk-tier base weights.
    stable_pct, primary_pct, secondary_pct = RISK_BASE_WEIGHTS[risk_level]

    # Momentum tilt: shift up to 10 points between the two indices based on 1m ROI gap.
    primary_roi = float((snap_primary or {}).get("1month_roi") or 0)
    secondary_roi = float((snap_secondary or {}).get("1month_roi") or 0)
    gap = primary_roi - secondary_roi
    tilt = max(-10, min(10, int(gap * 100)))  # 1% ROI gap = 1pt of tilt
    primary_pct += tilt
    secondary_pct -= tilt

    # ETF-flow risk-off: if BTC ETF cumulative inflow is negative, push 5pt to stable.
    last_inflow = None
    if etf and isinstance(etf, dict):
        last_inflow = etf.get("net_inflow")
        try:
            inflow_val = float(last_inflow) if last_inflow is not None else 0.0
        except (TypeError, ValueError):
            inflow_val = 0.0
        if inflow_val < 0 and risk_level != "low":
            stable_pct += 5
            primary_pct -= 3
            secondary_pct -= 2

    weights = _normalise_to_100([stable_pct, primary_pct, secondary_pct])
    stable_pct, primary_pct, secondary_pct = weights[0], weights[1], weights[2]

    # Compose allocations.
    allocations: list[dict[str, Any]] = [
        {
            "symbol": "USDC",
            "name": "USDC Stable Reserve",
            "percentage": stable_pct,
            "type": "Stable Reserve",
            "color": SYMBOL_COLORS["USDC"],
        },
        {
            "symbol": primary,
            "name": INDEX_DISPLAY.get(primary, primary.upper()),
            "percentage": primary_pct,
            "type": "Index",
            "oneMonthRoi": primary_roi,
            "oneYearRoi": float((snap_primary or {}).get("1year_roi") or 0),
            "color": SYMBOL_COLORS.get(primary, "#627EEA"),
        },
    ]
    if secondary != primary:
        allocations.append(
            {
                "symbol": secondary,
                "name": INDEX_DISPLAY.get(secondary, secondary.upper()),
                "percentage": secondary_pct,
                "type": "Index",
                "oneMonthRoi": secondary_roi,
                "oneYearRoi": float((snap_secondary or {}).get("1year_roi") or 0),
                "color": SYMBOL_COLORS.get(secondary, "#F7931A"),
            }
        )
    else:
        # Single-index fallback: roll secondary back into stable so weights still sum to 100.
        allocations[0]["percentage"] = stable_pct + secondary_pct

    # Recompute estimated blended annualised return from 1y ROI fields (USDC ~5%).
    blended = 0.0
    for alloc in allocations:
        weight = alloc["percentage"] / 100.0
        if alloc["type"] == "Stable Reserve":
            blended += weight * 0.05
        else:
            blended += weight * float(alloc.get("oneYearRoi") or 0)

    # Risk-tier-specific framing.
    summary, constraints, exec_steps = _tier_copy(risk_level, primary, secondary)

    sample_price = None
    if snap_primary and isinstance(snap_primary, dict):
        try:
            sample_price = float(snap_primary.get("price") or 0)
        except (TypeError, ValueError):
            sample_price = None

    try:
        last_inflow_float = float(last_inflow) if last_inflow is not None else None
    except (TypeError, ValueError):
        last_inflow_float = None

    return BasketResult(
        summary=summary,
        constraints=constraints,
        allocations=allocations,
        estimated_yield=round(blended, 4),
        estimated_gas=_tier_gas(risk_level),
        execution_steps=exec_steps,
        indices_used=[primary, secondary] if secondary != primary else [primary],
        sample_index_price=sample_price,
        last_etf_inflow=last_inflow_float,
    )


def _tier_copy(risk_level: str, primary: str, secondary: str) -> tuple[str, list[str], list[str]]:
    primary_disp = INDEX_DISPLAY.get(primary, primary.upper())
    secondary_disp = INDEX_DISPLAY.get(secondary, secondary.upper())

    if risk_level == "low":
        summary = (
            f"Capital-preserving basket: a 50%+ USDC reserve anchors the position with selective "
            f"exposure to {primary_disp} and a small {secondary_disp} sleeve."
        )
        constraints = [
            "Stable reserve floor of 40%",
            "Single-index exposure capped at 40%",
            "Auto-derisk on negative BTC ETF flows",
        ]
        steps = [
            "Approve USDC into PortfolioManager",
            "Mint SoSoVault shares at current NAV",
            "Quote target weights against SoDEX bookticker",
            "Submit BasketRebalanced(weights, symbols) for the on-chain audit trail",
        ]
    elif risk_level == "high":
        summary = (
            f"Aggressive growth basket leaning into {primary_disp} momentum, with a smaller "
            f"{secondary_disp} sleeve and a thin USDC buffer."
        )
        constraints = [
            f"{primary_disp} weight at least 50%",
            "Stable reserve no more than 20%",
            "4-hour rebalance cadence on signal change",
        ]
        steps = [
            "Approve USDC into PortfolioManager",
            "Mint SoSoVault shares at current NAV",
            f"Route 80%+ across {primary_disp} and {secondary_disp} via SoDEX bookticker",
            "Schedule 4h rebalance loop, emit BasketRebalanced event",
        ]
    else:  # medium
        summary = (
            f"Balanced basket: equal-weight {primary_disp} and {secondary_disp} exposure with a "
            f"meaningful USDC reserve to fund opportunistic rebalances."
        )
        constraints = [
            "Stable reserve between 25-35%",
            "Equal-weight major SoSoValue indices",
            "Trim positions with 7-day ROI below -8%",
        ]
        steps = [
            "Approve USDC into PortfolioManager",
            "Mint SoSoVault shares at current NAV",
            "Quote target weights against SoDEX bookticker",
            "Hold 30% USDC reserve, emit BasketRebalanced event",
        ]
    return summary, constraints, steps


def _tier_gas(risk_level: str) -> float:
    return {"low": 0.0038, "medium": 0.0045, "high": 0.0062}.get(risk_level, 0.0045)


def fallback_reasoning(risk_level: str, allocations: list[dict[str, Any]]) -> dict[str, str]:
    """Deterministic reasoning used when the LLM is unavailable."""
    risk_level = (risk_level or "medium").lower()
    primary = next((a for a in allocations if a["type"] == "Index"), None)
    primary_roi = (primary or {}).get("oneMonthRoi") or 0.0
    primary_name = (primary or {}).get("name") or "the lead index"

    if risk_level == "low":
        return {
            "volatility": (
                "ETF flow data is choppy and broader market volatility is elevated, so the "
                "basket biases toward USDC reserves while still capturing index drift."
            ),
            "yield": (
                f"Blended return is anchored by {primary_name} (1-month ROI "
                f"{primary_roi*100:+.1f}%) and a USDC sleeve earning a base ~5%."
            ),
            "risk": (
                "Drawdown exposure is bounded by the >40% stable reserve and a single-index cap; "
                "negative ETF flow days trigger an automatic 5-point shift back to USDC."
            ),
        }
    if risk_level == "high":
        return {
            "volatility": (
                f"The basket accepts wider price swings, prioritising {primary_name} momentum "
                f"capture (1-month ROI {primary_roi*100:+.1f}%)."
            ),
            "yield": (
                "Expected return is dominated by the lead SoSoValue index with a secondary index "
                "sleeve diversifying inside the volatile band."
            ),
            "risk": (
                "Real drawdown risk. The thin USDC buffer plus auto-trim on -8% 7-day ROI is the "
                "only safety net; rebalance cadence is 4h."
            ),
        }
    return {
        "volatility": (
            f"Index volatility is moderate; the basket leans into {primary_name} (1-month ROI "
            f"{primary_roi*100:+.1f}%) while keeping a 30% USDC reserve for rebalances."
        ),
        "yield": (
            "Weighted yield comes from two SoSoValue indices plus a stable sleeve providing dry "
            "powder for opportunistic rebalances."
        ),
        "risk": (
            "Concentration risk is controlled by equal-weighting two indices and a 30% USDC floor; "
            "news-triggered de-risk is enabled."
        ),
    }
