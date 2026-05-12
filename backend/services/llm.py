"""
Groq LLM client used to generate the basket reasoning prose.

We use Groq because it is free, fast, and ships strong instruction-following
Llama 3.x models. The model is configurable via `GROQ_MODEL`.

If `GROQ_API_KEY` is not set, the helper returns `None` so the caller can fall
back to deterministic templated reasoning. The demo never breaks if the key is
missing.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def _client():
    """Lazy import so the module loads even if `groq` is missing in dev."""
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[llm] groq import failed: {exc}")
        return None
    return Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = (
    "You are SoSoVault, an agentic on-chain fund manager that builds risk-tiered "
    "index baskets using SoSoValue indices, ETF flow data, and crypto news. "
    "You explain basket decisions to retail users in clear, calm, professional prose. "
    "You never invent numbers. When the user gives you live SoSoValue data, you ground "
    "every claim in that data."
)


def generate_reasoning(
    risk_level: str,
    allocations: list[dict[str, Any]],
    sosovalue_signals: dict[str, Any],
) -> tuple[Optional[dict[str, str]], dict[str, Any]]:
    """Generate volatility/yield/risk reasoning for a basket.

    Returns (reasoning_dict_or_None, meta_dict). `meta_dict` always contains
    `provider`, `model`, and `latency_ms` so the API response can show users
    which inference was used.
    """
    meta: dict[str, Any] = {
        "provider": "Groq" if GROQ_API_KEY else "templated",
        "model": DEFAULT_MODEL if GROQ_API_KEY else "deterministic",
        "latency_ms": 0,
    }

    client = _client()
    if client is None:
        return None, meta

    user_prompt = (
        f"Risk tier: {risk_level}\n"
        f"Target basket allocations:\n{json.dumps(allocations, indent=2)}\n"
        f"Live SoSoValue signals:\n{json.dumps(sosovalue_signals, indent=2)}\n\n"
        "Return ONLY a compact JSON object with three string fields, no markdown:\n"
        '{"volatility": "...", "yield": "...", "risk": "..."}\n'
        "Each field 1-2 sentences. Reference specific numbers from the data when "
        "possible (e.g. 1-month ROI, ETF inflow). Tone: confident, professional, "
        "calm. Never invent figures."
    )

    started = time.time()
    try:
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[llm] groq call failed: {exc}")
        meta["latency_ms"] = int((time.time() - started) * 1000)
        meta["error"] = str(exc)
        return None, meta

    meta["latency_ms"] = int((time.time() - started) * 1000)

    try:
        content = completion.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[llm] failed to parse groq output: {exc}")
        meta["error"] = f"parse: {exc}"
        return None, meta

    # Normalise keys
    out = {
        "volatility": str(parsed.get("volatility", "")).strip(),
        "yield": str(parsed.get("yield", "")).strip(),
        "risk": str(parsed.get("risk", "")).strip(),
    }
    if not all(out.values()):
        return None, meta
    return out, meta
