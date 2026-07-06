"""
Health check utilities for SoSoVault.

Provides detailed health status for monitoring and deployment.
"""
from __future__ import annotations

import time
from typing import Any

from . import database as db
from . import eip712
from .logging import get_logger

log = get_logger("health")

_start_time = time.time()


def get_uptime() -> float:
    """Return server uptime in seconds."""
    return time.time() - _start_time


def check_database() -> dict[str, Any]:
    """Check SQLite database connectivity."""
    try:
        conn = db.get_db()
        conn.execute("SELECT 1")
        return {"status": "ok", "path": db.DB_PATH}
    except Exception as exc:
        log.error("Database health check failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def check_sosovalue_api() -> dict[str, Any]:
    """Check SoSoValue API key is configured."""
    from . import sosovalue
    configured = bool(sosovalue.API_KEY)
    return {
        "status": "ok" if configured else "not_configured",
        "configured": configured,
    }


def check_sodex() -> dict[str, Any]:
    """Check SoDEX integration status."""
    return {
        "status": "ok" if eip712.is_configured() else "read_only",
        "configured": eip712.is_configured(),
        "chain_id": eip712.SODEX_CHAIN_ID,
    }


def full_health_check() -> dict[str, Any]:
    """Run all health checks and return comprehensive status."""
    db_health = check_database()
    sosovalue_health = check_sosovalue_api()
    sodex_health = check_sodex()

    all_ok = all(
        h.get("status") in ("ok", "read_only", "not_configured")
        for h in [db_health, sosovalue_health, sodex_health]
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "uptime_s": round(get_uptime(), 1),
        "checks": {
            "database": db_health,
            "sosovalue_api": sosovalue_health,
            "sodex": sodex_health,
        },
    }
