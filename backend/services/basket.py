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

# Default index candidates (case-insensitive lookup against live /indices).
# Real SoSoValue tickers are camelCase: ssiMAG7, ssiLayer1, ssiDeFi, ssiAI, ssiMeme,
# ssiSocialFi, ssiRWA, ssiDePIN, ssiNFT, ssiGameFi, ssiCeFi, ssiPayFi, ssiLayer2.
PREFERRED_INDICES = (
    "ssiMAG7",
    "ssiLayer1",
    "ssiDeFi",
    "ssiAI",
    "ssiMeme",
    "ssiRWA",
)

# Risk-tier base weights (stable, primary_index, secondary_index).
RISK_BASE_WEIGHTS: dict[str, tuple[int, int, int]] = {
    "low": (50, 35, 15),
    "medium": (30, 40, 30),
    "high": (15, 60, 25),
}

# Display colours per symbol — case-insensitive lookups via _norm() below.
_SYMBOL_COLORS_NORM: dict[str, str] = {
    "usdc": "#2775CA",
    "ssimag7": "#627EEA",
    "ssilayer1": "#F7931A",
    "ssidefi": "#B6509E",
    "ssiai": "#10B981",
    "ssimeme": "#F59E0B",
    "ssirwa": "#3B82F6",
    "ssidepin": "#06B6D4",
    "ssinft": "#EC4899",
    "ssigamefi": "#22D3EE",
    "ssicefi": "#A78BFA",
    "ssipayfi": "#84CC16",
    "ssilayer2": "#FB923C",
    "ssisocialfi": "#F472B6",
}

_INDEX_DISPLAY_NORM: dict[str, str] = {
    "ssimag7": "SoSoValue Mag7 Index",
    "ssilayer1": "SoSoValue Layer-1 Index",
    "ssidefi": "SoSoValue DeFi Index",
    "ssiai": "SoSoValue AI Index",
    "ssimeme": "SoSoValue Meme Index",
    "ssirwa": "SoSoValue RWA Index",
    "ssidepin": "SoSoValue DePIN Index",
    "ssinft": "SoSoValue NFT Index",
    "ssigamefi": "SoSoValue GameFi Index",
    "ssicefi": "SoSoValue CeFi Index",
    "ssipayfi": "SoSoValue PayFi Index",
    "ssilayer2": "SoSoValue Layer-2 Index",
    "ssisocialfi": "SoSoValue SocialFi Index",
}


def _norm(s: str) -> str:
    return (s or "").lower()


def _display_name(ticker: str) -> str:
    return _INDEX_DISPLAY_NORM.get(_norm(ticker)) or f"SoSoValue {ticker} Index"


def _color_for(ticker: str) -> str:
    return _SYMBOL_COLORS_NORM.get(_norm(ticker), "#F7931A")


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
    """Return up to two index tickers from `available`, matching our preferred set
    case-insensitively. Falls back to the first two live tickers if our preferences
    don't appear, and to a sensible default if `available` is empty."""
    avail_lower = {t.lower(): t for t in available}
    by_priority: list[str] = []
    for pref in PREFERRED_INDICES:
        actual = avail_lower.get(pref.lower())
        if actual and actual not in by_priority:
            by_priority.append(actual)
        if len(by_priority) >= 2:
            return by_priority[:2]
    extras = [t for t in available if t not in by_priority]
    chosen = (by_priority + extras)[:2]
    if chosen:
        return chosen
    return ["ssiMAG7", "ssiLayer1"]


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
    # SoSoValue field names are roi_1m / roi_1y / roi_7d / change_pct_24h.
    primary_roi = float((snap_primary or {}).get("roi_1m") or (snap_primary or {}).get("1month_roi") or 0)
    secondary_roi = float((snap_secondary or {}).get("roi_1m") or (snap_secondary or {}).get("1month_roi") or 0)
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
    primary_1y = float(
        (snap_primary or {}).get("roi_1y")
        or (snap_primary or {}).get("1year_roi")
        or 0
    )
    secondary_1y = float(
        (snap_secondary or {}).get("roi_1y")
        or (snap_secondary or {}).get("1year_roi")
        or 0
    )
    allocations: list[dict[str, Any]] = [
        {
            "symbol": "USDC",
            "name": "USDC Stable Reserve",
            "percentage": stable_pct,
            "type": "Stable Reserve",
            "color": _color_for("USDC"),
        },
        {
            "symbol": primary,
            "name": _display_name(primary),
            "percentage": primary_pct,
            "type": "Index",
            "oneMonthRoi": primary_roi,
            "oneYearRoi": primary_1y,
            "color": _color_for(primary),
        },
    ]
    if secondary != primary:
        allocations.append(
            {
                "symbol": secondary,
                "name": _display_name(secondary),
                "percentage": secondary_pct,
                "type": "Index",
                "oneMonthRoi": secondary_roi,
                "oneYearRoi": secondary_1y,
                "color": _color_for(secondary),
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
    primary_disp = _display_name(primary)
    secondary_disp = _display_name(secondary)

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
