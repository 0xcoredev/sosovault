"""
Signals feed builder.

Turns raw SoSoValue data (ETF flows, index ROI, news sentiment heuristics) into a list
of `SignalItem` objects that the frontend Signals page renders. Each signal has a
`suggested_action` string the user can act on with one click ("Apply to my basket").

This is intentionally rule-based for Wave 1 — clear, explainable, fast. Wave 2 will
swap the heuristic news classifier for a Groq-powered sentiment pass.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from . import sosovalue

NEWS_BULL_KEYWORDS = (
    "approves", "approval", "approved", "etf", "rally", "surge", "all-time", "ath",
    "record", "inflow", "buy", "bullish", "upgrade", "launches", "partnership", "wins",
)
NEWS_BEAR_KEYWORDS = (
    "hack", "exploit", "drain", "collapse", "lawsuit", "sec", "ban", "outflow", "crash",
    "bearish", "downgrade", "rejected", "pause", "halts", "delist", "fraud", "fine",
)


def _signal_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def _classify_news_title(title: str) -> str:
    t = title.lower()
    if any(re.search(rf"\b{kw}\b", t) for kw in NEWS_BEAR_KEYWORDS):
        return "bearish"
    if any(re.search(rf"\b{kw}\b", t) for kw in NEWS_BULL_KEYWORDS):
        return "bullish"
    return "neutral"


async def build_signals_feed(news_limit: int = 8) -> dict[str, Any]:
    """Build the full signals feed used by the Signals page."""
    indices_task = asyncio.create_task(sosovalue.list_indices())
    etf_task = asyncio.create_task(sosovalue.etf_snapshot("IBIT"))
    news_task = asyncio.create_task(sosovalue.news(page=1, page_size=news_limit))
    indices, etf, news_payload = await asyncio.gather(indices_task, etf_task, news_task)

    signals: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    # 1. ETF flow signal (BTC IBIT)
    if etf and isinstance(etf, dict):
        try:
            net = float(etf.get("net_inflow") or 0)
            cum = float(etf.get("cum_inflow") or 0)
        except (TypeError, ValueError):
            net = cum = 0.0
        direction = "bullish" if net > 0 else "bearish" if net < 0 else "neutral"
        if direction == "bullish":
            action = "+5% ssimag7 / -5% USDC"
            confidence = 0.74
        elif direction == "bearish":
            action = "+5% USDC / -5% ssimag7"
            confidence = 0.78
        else:
            action = "Hold current weights"
            confidence = 0.55
        signals.append(
            {
                "id": _signal_id(f"etf-IBIT-{etf.get('date')}"),
                "kind": "etf_flow",
                "direction": direction,
                "asset": "BTC",
                "headline": f"BTC spot ETF (IBIT) {direction} flow signal",
                "detail": (
                    f"IBIT net inflow {net:,.0f} USD, cumulative {cum:,.0f} USD. "
                    f"This biases the basket {direction}."
                ),
                "confidence": confidence,
                "suggested_action": action,
                "generated_at": now,
            }
        )

    # 2. Index momentum signals (1-month ROI on top 2 available)
    chosen_indices: list[str] = []
    for ticker in ("ssimag7", "ssilayer1", "ssidefi", "ssiai"):
        if ticker in indices:
            chosen_indices.append(ticker)
        if len(chosen_indices) >= 2:
            break

    for ticker in chosen_indices:
        snap = await sosovalue.index_snapshot(ticker)
        if not snap or not isinstance(snap, dict):
            continue
        try:
            roi_1m = float(snap.get("1month_roi") or 0)
            change_24h = float(snap.get("24h_change_pct") or 0)
        except (TypeError, ValueError):
            roi_1m = change_24h = 0.0
        if roi_1m >= 0.04:
            direction = "bullish"
            action = f"+5% {ticker} / -5% USDC"
            confidence = min(0.9, 0.6 + roi_1m * 2)
        elif roi_1m <= -0.04:
            direction = "bearish"
            action = f"-5% {ticker} / +5% USDC"
            confidence = min(0.9, 0.6 + abs(roi_1m) * 2)
        else:
            direction = "neutral"
            action = f"Hold {ticker} weight"
            confidence = 0.55
        signals.append(
            {
                "id": _signal_id(f"momentum-{ticker}-{roi_1m:.4f}"),
                "kind": "index_momentum",
                "direction": direction,
                "asset": ticker,
                "headline": f"{ticker} 1-month ROI {roi_1m*100:+.1f}%",
                "detail": (
                    f"24h change {change_24h*100:+.2f}%. Momentum is {direction}; "
                    f"the basket builder applies a tilt of up to ±10pt based on this gap."
                ),
                "confidence": round(confidence, 2),
                "suggested_action": action,
                "generated_at": now,
            }
        )

    # 3. News sentiment signals (top headlines).
    news_list_raw = (news_payload or {}).get("list") or []
    news_compact: list[dict[str, Any]] = []
    bull_count = bear_count = 0
    for item in news_list_raw[:news_limit]:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        verdict = _classify_news_title(title)
        if verdict == "bullish":
            bull_count += 1
        elif verdict == "bearish":
            bear_count += 1
        news_compact.append(
            {
                "id": str(item.get("id") or _signal_id(title)),
                "title": title,
                "release_time": item.get("release_time") or 0,
                "source_link": item.get("source_link") or item.get("original_link") or "",
                "verdict": verdict,
            }
        )

    if news_compact:
        if bear_count > bull_count + 1:
            direction = "bearish"
            action = "+3% USDC / -3% ssimag7"
            headline = "News sentiment skews bearish"
            confidence = 0.66
        elif bull_count > bear_count + 1:
            direction = "bullish"
            action = "+3% ssimag7 / -3% USDC"
            headline = "News sentiment skews bullish"
            confidence = 0.66
        else:
            direction = "neutral"
            action = "Hold current weights"
            headline = "News sentiment is mixed"
            confidence = 0.5
        signals.append(
            {
                "id": _signal_id(f"news-{bull_count}-{bear_count}"),
                "kind": "news_sentiment",
                "direction": direction,
                "asset": "macro",
                "headline": headline,
                "detail": (
                    f"Of {len(news_compact)} latest SoSoValue headlines: "
                    f"{bull_count} bullish, {bear_count} bearish."
                ),
                "confidence": confidence,
                "suggested_action": action,
                "generated_at": now,
            }
        )

    return {
        "signals": signals,
        "news": news_compact,
        "generated_at": now,
    }
