"""Configuration centralisée. Tout secret vient de l'environnement, jamais du code."""
from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Mini-chargeur .env (évite une dépendance). N'écrase pas les variables déjà définies."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
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
    # Pas de clé par défaut codée en dur : une clé aléatoire par processus.
    # Conséquence voulue : les tokens expirent à chaque redémarrage.
    print("[config] SECRET_KEY absente ou trop courte : clé aléatoire générée pour ce processus.", file=sys.stderr)
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", str(ROOT / "moments.db"))))
    secret_key: str = field(default_factory=_secret_key)
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "60"))
    # Horloge de démo : toutes les données synthétiques sont ancrées sur cette date.
    demo_now: datetime = field(
        default_factory=lambda: datetime.fromisoformat(os.getenv("DEMO_NOW", "2026-10-01T10:30:00"))
    )
    # Rendu LLM (optionnel : sans clé, le moteur utilise des gabarits validés)
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    # Voix (optionnel : sans clé, le navigateur lit le texte avec la synthèse vocale locale)
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))
    elevenlabs_model: str = field(default_factory=lambda: os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"))
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()
        )
    )
    # Mode démo : expose le journal du moteur au client (transparence pour le jury).
    # En production : False, le journal n'est visible que par les conseillers.
    demo_mode: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")
    enable_docs: bool = field(default_factory=lambda: os.getenv("ENABLE_DOCS", "false").lower() == "true")
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_window_seconds: int = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
    audio_cache_dir: Path = field(default_factory=lambda: ROOT / ".cache" / "audio")


settings = Settings()
