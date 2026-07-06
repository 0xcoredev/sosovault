"""
Application configuration for SoSoVault.

Centralizes all env var reads with sensible defaults.
"""
from __future__ import annotations

import os


class Config:
    """App configuration loaded from environment variables."""

    # Server
    PORT: int = int(os.getenv("PORT", "3001"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

    # Rate limiting
    RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "60"))
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "10"))

    # SoSoValue API
    SOSOVALUE_API_KEY: str = os.getenv("SOSOVALUE_API_KEY", "")
    SOSOVALUE_BASE_URL: str = os.getenv(
        "SOSOVALUE_BASE_URL", "https://openapi.sosovalue.com/openapi/v1"
    )
    SOSOVALUE_CACHE_TTL: int = int(os.getenv("SOSOVALUE_CACHE_TTL_S", "60"))
    SOSOVALUE_TIMEOUT: float = float(os.getenv("SOSOVALUE_TIMEOUT_S", "8"))

    # SoDEX
    SODEX_BASE_URL: str = os.getenv("SODEX_BASE_URL", "https://testnet-gw.sodex.dev")
    SODEX_PRIVATE_KEY: str = os.getenv("SODEX_PRIVATE_KEY", "")
    SODEX_ADDRESS: str = os.getenv("SODEX_ADDRESS", "")
    SODEX_ACCOUNT_ID: int = int(os.getenv("SODEX_ACCOUNT_ID", "0"))
    SODEX_CHAIN_ID: int = int(os.getenv("SODEX_CHAIN_ID", "138565"))
    SODEX_TIMEOUT: float = float(os.getenv("SODEX_TIMEOUT_S", "15"))

    # Groq LLM
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Database
    DB_PATH: str = os.getenv("SOVAULT_DB_PATH", "sosovault.db")

    # Scanner
    SCANNER_INTERVAL: int = int(os.getenv("SCANNER_INTERVAL_S", "300"))


config = Config()
