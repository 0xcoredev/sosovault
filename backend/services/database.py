"""
SQLite database layer for SoSoVault Wave 2.

Tables:
  - signals       AI-generated trading signals with entry/TP/SL and outcome tracking
  - trades        Executed trades with fill details
  - agent_logs    Timestamped agent activity + results
  - portfolio_snapshots  Daily portfolio value snapshots
  - wallets       Per-address wallet metadata

Zero external dependencies — Python's built-in sqlite3 via aiosqlite.
"""
from __future__ import annotations

import json
import os
import sqlite3
import datetime
from typing import Any, Optional

DB_PATH = os.getenv("SOVAULT_DB_PATH", "sosovault.db")

_connection: Optional[sqlite3.Connection] = None


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        _init_tables(_connection)
    return _connection


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            direction TEXT NOT NULL,
            asset TEXT NOT NULL,
            headline TEXT NOT NULL,
            detail TEXT NOT NULL,
            confidence REAL NOT NULL,
            suggested_action TEXT NOT NULL,
            entry_price REAL,
            take_profit REAL,
            stop_loss REAL,
            outcome TEXT DEFAULT 'PENDING',
            outcome_price REAL,
            outcome_at TEXT,
            generated_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            signal_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL DEFAULT 'LIMIT_IOC',
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            notional REAL NOT NULL,
            sodex_order_id TEXT,
            tx_hash TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            filled_at TEXT,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            input_data TEXT,
            output_data TEXT,
            success INTEGER NOT NULL DEFAULT 1,
            latency_ms INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            total_value REAL NOT NULL,
            allocations TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wallets (
            address TEXT PRIMARY KEY,
            label TEXT,
            risk_level TEXT DEFAULT 'medium',
            auto_rebalance INTEGER DEFAULT 0,
            rebalance_threshold REAL DEFAULT 0.7,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome);
        CREATE INDEX IF NOT EXISTS idx_signals_generated ON signals(generated_at);
        CREATE INDEX IF NOT EXISTS idx_trades_address ON trades(address);
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent);
        CREATE INDEX IF NOT EXISTS idx_snapshots_address ON portfolio_snapshots(address);
    """)
    conn.commit()


# --------------------------------------------------------------------------- #
# Signal CRUD                                                                 #
# --------------------------------------------------------------------------- #

def insert_signal(signal: dict[str, Any]) -> str:
    db = get_db()
    db.execute(
        """INSERT OR REPLACE INTO signals
           (id, kind, direction, asset, headline, detail, confidence,
            suggested_action, entry_price, take_profit, stop_loss, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            signal["id"], signal["kind"], signal["direction"], signal["asset"],
            signal["headline"], signal["detail"], signal["confidence"],
            signal["suggested_action"],
            signal.get("entry_price"), signal.get("take_profit"),
            signal.get("stop_loss"), signal["generated_at"],
        ),
    )
    db.commit()
    return signal["id"]


def update_signal_outcome(signal_id: str, outcome: str, outcome_price: float) -> None:
    db = get_db()
    db.execute(
        "UPDATE signals SET outcome=?, outcome_price=?, outcome_at=? WHERE id=?",
        (outcome, outcome_price, _now_iso(), signal_id),
    )
    db.commit()


def get_pending_signals() -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM signals WHERE outcome='PENDING' ORDER BY generated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_signals_with_outcomes(limit: int = 50) -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_signal_stats() -> dict[str, Any]:
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    hit = db.execute("SELECT COUNT(*) FROM signals WHERE outcome='HIT'").fetchone()[0]
    stop = db.execute("SELECT COUNT(*) FROM signals WHERE outcome='STOP'").fetchone()[0]
    drift = db.execute("SELECT COUNT(*) FROM signals WHERE outcome='DRIFT'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM signals WHERE outcome='PENDING'").fetchone()[0]
    resolved = hit + stop + drift
    return {
        "total": total,
        "hit": hit,
        "stop": stop,
        "drift": drift,
        "pending": pending,
        "win_rate": round(hit / resolved, 4) if resolved > 0 else 0,
        "resolved": resolved,
    }


# --------------------------------------------------------------------------- #
# Trade CRUD                                                                  #
# --------------------------------------------------------------------------- #

def insert_trade(trade: dict[str, Any]) -> int:
    db = get_db()
    cursor = db.execute(
        """INSERT INTO trades
           (address, signal_id, symbol, side, order_type, quantity, price,
            notional, sodex_order_id, tx_hash, status, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade["address"], trade.get("signal_id"), trade["symbol"],
            trade["side"], trade.get("order_type", "LIMIT_IOC"),
            trade["quantity"], trade["price"], trade["notional"],
            trade.get("sodex_order_id"), trade.get("tx_hash"),
            trade.get("status", "PENDING"), trade.get("error_message"),
        ),
    )
    db.commit()
    return cursor.lastrowid


def update_trade_status(trade_id: int, status: str, sodex_order_id: str = None,
                        tx_hash: str = None, error_message: str = None) -> None:
    db = get_db()
    filled_at = _now_iso() if status == "FILLED" else None
    db.execute(
        """UPDATE trades SET status=?, sodex_order_id=?, tx_hash=?,
           error_message=?, filled_at=? WHERE id=?""",
        (status, sodex_order_id, tx_hash, error_message, filled_at, trade_id),
    )
    db.commit()


def get_trades(address: str = None, limit: int = 50) -> list[dict[str, Any]]:
    db = get_db()
    if address:
        rows = db.execute(
            "SELECT * FROM trades WHERE address=? ORDER BY created_at DESC LIMIT ?",
            (address, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_trade_stats() -> dict[str, Any]:
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    filled = db.execute("SELECT COUNT(*) FROM trades WHERE status='FILLED'").fetchone()[0]
    failed = db.execute("SELECT COUNT(*) FROM trades WHERE status='FAILED'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM trades WHERE status='PENDING'").fetchone()[0]
    total_notional = db.execute(
        "SELECT COALESCE(SUM(notional), 0) FROM trades WHERE status='FILLED'"
    ).fetchone()[0]
    return {
        "total": total,
        "filled": filled,
        "failed": failed,
        "pending": pending,
        "total_notional": round(float(total_notional), 2),
    }


# --------------------------------------------------------------------------- #
# Agent Logs                                                                  #
# --------------------------------------------------------------------------- #

def log_agent_action(agent: str, action: str, input_data: Any = None,
                     output_data: Any = None, success: bool = True,
                     latency_ms: int = None) -> int:
    db = get_db()
    cursor = db.execute(
        """INSERT INTO agent_logs (agent, action, input_data, output_data, success, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            agent, action,
            json.dumps(input_data) if input_data else None,
            json.dumps(output_data) if output_data else None,
            1 if success else 0, latency_ms,
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_agent_logs(agent: str = None, limit: int = 50) -> list[dict[str, Any]]:
    db = get_db()
    if agent:
        rows = db.execute(
            "SELECT * FROM agent_logs WHERE agent=? ORDER BY created_at DESC LIMIT ?",
            (agent, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM agent_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Portfolio Snapshots                                                         #
# --------------------------------------------------------------------------- #

def insert_snapshot(address: str, total_value: float, allocations: list[dict]) -> int:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO portfolio_snapshots (address, total_value, allocations) VALUES (?, ?, ?)",
        (address, total_value, json.dumps(allocations)),
    )
    db.commit()
    return cursor.lastrowid


def get_snapshots(address: str, limit: int = 30) -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM portfolio_snapshots WHERE address=? ORDER BY created_at DESC LIMIT ?",
        (address, limit),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["allocations"] = json.loads(d["allocations"])
        result.append(d)
    return result


# --------------------------------------------------------------------------- #
# Wallets                                                                     #
# --------------------------------------------------------------------------- #

def upsert_wallet(address: str, label: str = None, risk_level: str = "medium",
                  auto_rebalance: bool = False, rebalance_threshold: float = 0.7) -> None:
    db = get_db()
    db.execute(
        """INSERT INTO wallets (address, label, risk_level, auto_rebalance, rebalance_threshold, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(address) DO UPDATE SET
             label=COALESCE(excluded.label, wallets.label),
             risk_level=excluded.risk_level,
             auto_rebalance=excluded.auto_rebalance,
             rebalance_threshold=excluded.rebalance_threshold,
             updated_at=excluded.updated_at""",
        (address, label, risk_level, 1 if auto_rebalance else 0,
         rebalance_threshold, _now_iso()),
    )
    db.commit()


def get_wallet(address: str) -> Optional[dict[str, Any]]:
    db = get_db()
    row = db.execute("SELECT * FROM wallets WHERE address=?", (address,)).fetchone()
    return dict(row) if row else None


def get_wallets_with_auto_rebalance() -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute("SELECT * FROM wallets WHERE auto_rebalance=1").fetchall()
    return [dict(r) for r in rows]
