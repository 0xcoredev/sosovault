"""
Signal outcome tracker and background scanner.

Periodically scans pending signals against live SoSoValue prices to classify
them as HIT (target reached), STOP (stop-loss triggered), or DRIFT (expired).

Also runs a background loop that:
  1. Generates new signals from live data every 5 minutes
  2. Checks pending signal outcomes every 2 minutes
  3. Logs all agent actions to SQLite
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from . import database as db
from . import signals as signals_svc
from . import sosovalue


async def evaluate_signal_outcome(signal: dict[str, Any]) -> str:
    """Check if a pending signal has hit its target, stop-loss, or drifted.

    Classification:
      HIT   — price moved in the predicted direction by >= confidence * 5%
      STOP  — price moved against the prediction by >= 3%
      DRIFT — signal is older than 24h and neither HIT nor STOP
      PENDING — still within time window, no resolution yet
    """
    asset = signal.get("asset", "")
    direction = signal.get("direction", "neutral")
    entry_price = signal.get("entry_price")
    confidence = signal.get("confidence", 0.5)
    generated_at = signal.get("generated_at", "")

    if direction == "neutral":
        return "DRIFT"

    # Get current price for the asset
    current_price = None
    if asset.lower() in ("btc", "ssimag7"):
        snap = await sosovalue.index_snapshot("ssiMAG7")
        if snap:
            try:
                current_price = float(snap.get("price") or 0)
            except (TypeError, ValueError):
                pass
    elif asset.lower() in ("eth", "ssilayer1"):
        snap = await sosovalue.index_snapshot("ssiLayer1")
        if snap:
            try:
                current_price = float(snap.get("price") or 0)
            except (TypeError, ValueError):
                pass
    elif asset.lower().startswith("ssi"):
        snap = await sosovalue.index_snapshot(asset)
        if snap:
            try:
                current_price = float(snap.get("price") or 0)
            except (TypeError, ValueError):
                pass
    elif asset.lower() == "macro":
        return "DRIFT"

    if current_price is None or current_price <= 0:
        return "PENDING"

    if entry_price is None or entry_price <= 0:
        return "PENDING"

    pct_change = (current_price - entry_price) / entry_price

    # HIT threshold scales with confidence (min 2%, max 8%)
    hit_threshold = max(0.02, min(0.08, confidence * 0.08))
    stop_threshold = -0.03

    if direction == "bullish":
        if pct_change >= hit_threshold:
            return "HIT"
        if pct_change <= stop_threshold:
            return "STOP"
    elif direction == "bearish":
        if pct_change <= -hit_threshold:
            return "HIT"
        if pct_change >= abs(stop_threshold):
            return "STOP"

    # Check if signal is older than 24h — classify as DRIFT
    try:
        gen_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - gen_time).total_seconds() / 3600
        if age_hours > 24:
            return "DRIFT"
    except (ValueError, TypeError):
        pass

    return "PENDING"


async def scan_pending_signals() -> dict[str, Any]:
    """Evaluate all pending signals and update their outcomes in the DB."""
    pending = db.get_pending_signals()
    results = {"scanned": 0, "hit": 0, "stop": 0, "drift": 0, "pending": 0}

    for signal in pending:
        outcome = await evaluate_signal_outcome(signal)
        results["scanned"] += 1

        if outcome in ("HIT", "STOP", "DRIFT"):
            # Get the current price for the outcome record
            asset = signal.get("asset", "")
            outcome_price = 0.0
            if asset.lower().startswith("ssi"):
                snap = await sosovalue.index_snapshot(asset)
                if snap:
                    try:
                        outcome_price = float(snap.get("price") or 0)
                    except (TypeError, ValueError):
                        pass

            db.update_signal_outcome(signal["id"], outcome, outcome_price)
            results[outcome.lower()] += 1
        else:
            results["pending"] += 1

    db.log_agent_action(
        agent="signal_tracker",
        action="scan_pending",
        input_data={"pending_count": len(pending)},
        output_data=results,
        success=True,
    )
    return results


async def generate_and_store_signals() -> dict[str, Any]:
    """Generate fresh signals from live data and store them in the DB."""
    t0 = time.time()
    feed = await signals_svc.build_signals_feed(news_limit=8)
    stored = 0

    for signal in feed.get("signals", []):
        # Get current price as entry price for new signals
        asset = signal.get("asset", "")
        entry_price = None
        if asset.lower().startswith("ssi"):
            snap = await sosovalue.index_snapshot(asset)
            if snap:
                try:
                    entry_price = float(snap.get("price") or 0)
                except (TypeError, ValueError):
                    pass

        signal["entry_price"] = entry_price
        signal["take_profit"] = None
        signal["stop_loss"] = None

        # Set TP/SL based on direction and confidence
        if entry_price and signal.get("direction") == "bullish":
            conf = signal.get("confidence", 0.5)
            signal["take_profit"] = round(entry_price * (1 + conf * 0.08), 2)
            signal["stop_loss"] = round(entry_price * 0.97, 2)
        elif entry_price and signal.get("direction") == "bearish":
            conf = signal.get("confidence", 0.5)
            signal["take_profit"] = round(entry_price * (1 - conf * 0.08), 2)
            signal["stop_loss"] = round(entry_price * 1.03, 2)

        db.insert_signal(signal)
        stored += 1

    latency_ms = int((time.time() - t0) * 1000)
    db.log_agent_action(
        agent="signal_scanner",
        action="generate_signals",
        input_data={"news_limit": 8},
        output_data={"stored": stored, "latency_ms": latency_ms},
        success=True,
        latency_ms=latency_ms,
    )
    return {"stored": stored, "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

_scanner_task: asyncio.Task | None = None
_running = False


async def _scanner_loop(interval_s: int = 300) -> None:
    """Background loop: generate signals every `interval_s` seconds, check outcomes every 2 min."""
    global _running
    _running = True
    last_generate = 0.0
    last_scan = 0.0

    while _running:
        now = time.time()

        # Generate new signals every interval_s (default 5 min)
        if now - last_generate >= interval_s:
            try:
                await generate_and_store_signals()
                last_generate = now
            except Exception as exc:
                print(f"[scanner] generate error: {exc}")
                db.log_agent_action(
                    agent="signal_scanner",
                    action="generate_error",
                    output_data={"error": str(exc)},
                    success=False,
                )

        # Check signal outcomes every 2 minutes
        if now - last_scan >= 120:
            try:
                await scan_pending_signals()
                last_scan = now
            except Exception as exc:
                print(f"[scanner] scan error: {exc}")

        await asyncio.sleep(30)


def start_background_scanner(interval_s: int = 300) -> None:
    global _scanner_task
    if _scanner_task is not None and not _scanner_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
        _scanner_task = loop.create_task(_scanner_loop(interval_s))
        print(f"[scanner] Background signal scanner started (interval={interval_s}s)")
    except RuntimeError:
        print("[scanner] No event loop running — scanner will start on first request")


def stop_background_scanner() -> None:
    global _running, _scanner_task
    _running = False
    if _scanner_task is not None:
        _scanner_task.cancel()
        _scanner_task = None
