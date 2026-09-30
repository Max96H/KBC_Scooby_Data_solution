"""Minimal Gemini client (REST). The LLM rewrites, it never decides.

Deliberately minimal input: the chosen action, the validated reference text, the language, the tone,
the channel and an age band. No transaction, no amount, no customer identifier.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.render.schema import GEMINI_RESPONSE_SCHEMA, LlmCopy

log = logging.getLogger("moments.llm")

SYSTEM_PROMPT = """You write short messages for the app of a Belgian bank-insurer.
Strict rules:
- You rewrite the REFERENCE TEXT you are given. You add no fact, no product, no figure, no rate, no promise.
- No HTML, no link, no emoji. The only template allowed is {first_name}.
- Title: 80 characters max. Body: 2 to 3 sentences, 380 characters max. Push: one sentence, 100 characters max.
- Tone "warm": warm and human. Tone "direct": sober and factual. Never sales pressure, never artificial urgency.
- If the channel is "voice", write to be read aloud: short sentences, no brackets.
- Write in the requested language: en (English), fr (French) or nl (Dutch).
- If a reference list is provided, rewrite it as 3 to 5 short items, adding no information.
Answer only with the requested JSON."""


def build_prompt(action_id: str, family: str, moment: str, language: str, variant: str, age_band: str,
                 channel: str, reference: dict) -> str:
    payload = {
        "action": action_id, "family": family, "moment": moment, "language": language, "tone": variant,
        "age_band": age_band, "channel": channel, "reference_text": reference,
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_copy(prompt: str) -> LlmCopy | None:
    """Return validated copy, or None (the renderer then falls back to the template)."""
    if not settings.gemini_api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_RESPONSE_SCHEMA,
            "maxOutputTokens": 700,
        },
    }
    try:
        r = httpx.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key}, timeout=10.0)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return LlmCopy.model_validate(json.loads(text))
    except Exception as exc:  # network, quota, invalid JSON, validation: never break the screen
        log.warning("LLM output rejected, template used: %s", type(exc).__name__)
        return None
