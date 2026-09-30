"""Central configuration. Every secret comes from the environment, never from the code."""
from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ("en", "fr", "nl")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (avoids a dependency). Never overrides variables that are already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "")
    if len(key) >= 32:
        return key
    # No hard-coded default key: a random key per process.
    # Intended consequence: tokens are invalidated on every restart.
    print("[config] SECRET_KEY missing or too short: a random key was generated for this process.", file=sys.stderr)
    return secrets.token_urlsafe(48)


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in os.getenv(name, default).split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", str(ROOT / "moments.db"))))
    secret_key: str = field(default_factory=_secret_key)
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "60"))
    # Demo clock: all synthetic data is anchored on this date.
    demo_now: datetime = field(default_factory=lambda: datetime.fromisoformat(os.getenv("DEMO_NOW", "2026-10-01T10:30:00")))
    # LLM rendering (optional: without a key, the engine uses validated templates)
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    # Voice (optional: without a key, the browser reads the text with its own speech synthesis)
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))
    elevenlabs_model: str = field(default_factory=lambda: os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"))
    # Host header allow-list (defence against Host header injection)
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: _csv("ALLOWED_HOSTS", "localhost,127.0.0.1"))
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: _csv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"))
    # Demo mode: exposes the engine journal to the customer (transparency for the jury).
    # In production: False, the journal is only visible to advisors.
    demo_mode: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")
    enable_docs: bool = field(default_factory=lambda: os.getenv("ENABLE_DOCS", "false").lower() == "true")
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_window_seconds: int = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
    audio_cache_dir: Path = field(default_factory=lambda: ROOT / ".cache" / "audio")


settings = Settings()
