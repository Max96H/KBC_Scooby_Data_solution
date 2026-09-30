"""Client Gemini minimal (REST). Le LLM reformule, il ne décide jamais.

Entrée volontairement minimale : l'action choisie, le texte de référence validé, la langue, le ton,
une tranche d'âge. Aucune transaction, aucun montant, aucun identifiant client.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.render.schema import GEMINI_RESPONSE_SCHEMA, LlmCopy

log = logging.getLogger("moments.llm")

SYSTEM_PROMPT = """Tu rédiges des messages courts pour l'application d'une banque-assurance belge.
Règles strictes :
- Tu reformules le TEXTE DE RÉFÉRENCE fourni. Tu n'ajoutes aucun fait, aucun produit, aucun chiffre, aucun taux, aucune promesse.
- Pas de HTML, pas de lien, pas d'emoji. Le seul gabarit autorisé est {first_name}.
- Titre : 80 caractères maximum. Corps : 2 à 3 phrases, 380 caractères maximum.
- Ton "warm" : chaleureux et humain. Ton "direct" : sobre et factuel. Jamais de pression commerciale, jamais d'urgence artificielle.
- Si le canal est "voice", écris pour être lu à voix haute : phrases courtes, pas de parenthèses.
- Écris dans la langue demandée (fr ou nl).
- Si une liste de référence est fournie, reformule-la en 3 à 5 éléments courts, sans ajouter d'information.
Réponds uniquement avec le JSON demandé."""


def build_prompt(action_id: str, family: str, moment: str, language: str, variant: str, age_band: str,
                 channel: str, reference: dict) -> str:
    payload = {
        "action": action_id, "famille": family, "moment": moment, "langue": language, "ton": variant,
        "tranche_age": age_band, "canal": channel, "texte_de_reference": reference,
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_copy(prompt: str) -> LlmCopy | None:
    """Retourne une copie validée, ou None (le renderer bascule alors sur le gabarit)."""
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
            "maxOutputTokens": 600,
        },
    }
    try:
        r = httpx.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key}, timeout=10.0)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return LlmCopy.model_validate(json.loads(text))
    except Exception as exc:  # réseau, quota, JSON invalide, validation : on ne casse jamais l'écran
        log.warning("Rendu LLM rejeté, gabarit utilisé : %s", type(exc).__name__)
        return None
