"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    secret: str = field(default_factory=lambda: os.environ.get("ASCLEPIUS_SECRET", "dev-only-secret-change-me"))
    db_path: str = field(default_factory=lambda: os.environ.get("ASCLEPIUS_DB", ":memory:"))
    seed: int = field(default_factory=lambda: int(os.environ.get("ASCLEPIUS_SEED", "2026")))
    n_patients: int = field(default_factory=lambda: int(os.environ.get("ASCLEPIUS_PATIENTS", "64")))
    demo_auth: bool = field(default_factory=lambda: _bool("ASCLEPIUS_DEMO_AUTH", True))
    token_ttl_s: int = field(default_factory=lambda: int(os.environ.get("ASCLEPIUS_TOKEN_TTL", "28800")))
    break_glass_minutes: int = field(default_factory=lambda: int(os.environ.get("ASCLEPIUS_BTG_MINUTES", "60")))
    llm_url: str = field(default_factory=lambda: os.environ.get("ASCLEPIUS_LLM_URL", ""))
    llm_model: str = field(default_factory=lambda: os.environ.get("ASCLEPIUS_LLM_MODEL", "llama3.1"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.environ.get("ASCLEPIUS_CORS", "http://localhost:3000").split(",") if o.strip()
        )
    )


def get_settings() -> Settings:
    return Settings()
