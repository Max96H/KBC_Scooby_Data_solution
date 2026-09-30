"""Canal voix via ElevenLabs (bonus). Sans clé API, le front lit le texte avec la synthèse vocale du navigateur.

L'audio est mis en cache sur disque par empreinte du texte : un même message (générique par segment)
n'est synthétisé qu'une fois, ce qui garde le coût maîtrisé à grande échelle.
"""
from __future__ import annotations

import hashlib
import logging

import httpx

from app.config import settings

log = logging.getLogger("moments.voice")
MAX_CHARS = 700


def synthesize(text: str) -> bytes | None:
    if not settings.elevenlabs_api_key or not text:
        return None
    text = text[:MAX_CHARS]
    key = hashlib.sha256(f"{settings.elevenlabs_voice_id}|{settings.elevenlabs_model}|{text}".encode()).hexdigest()
    cache_dir = settings.audio_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.mp3"
    if path.exists():
        return path.read_bytes()
    try:
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": settings.elevenlabs_model,
                  "voice_settings": {"stability": 0.6, "similarity_boost": 0.75}},
            timeout=20.0,
        )
        r.raise_for_status()
    except Exception as exc:
        log.warning("Synthèse vocale indisponible : %s", type(exc).__name__)
        return None
    path.write_bytes(r.content)
    return r.content
