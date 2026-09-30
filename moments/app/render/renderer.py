"""Étage 4 : transformer la décision en écran.

1. Texte : cache (action × segment × langue × variante × canal) -> sinon LLM validé -> sinon gabarit.
   Le texte mis en cache est générique (gabarit {first_name}) : il est réutilisé pour tout le segment.
2. Structure : assemblée par le serveur à partir de types de blocs connus.
3. Panneau « pourquoi je vois ça » : construit depuis le journal du moteur, jamais par le LLM.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.engine.catalog import FAMILIES, get_action
from app.engine.decision import ABSTAIN_REASON_TEXT, Decision
from app.engine.features import CONSENT_FAMILIES, Snapshot
from app.engine.feedback import age_band
from app.engine.signals import EVIDENCE_TEXT
from app.render import llm
from app.render.templates import template_copy

RENDER_VERSION = "v1"

UI_TEXT = {
    "why_title": {"fr": "Pourquoi je vois ça ?", "nl": "Waarom zie ik dit?"},
    "excluded": {"fr": "{n} transaction(s) liées à la santé ou à des convictions ont été exclues et ne sont jamais analysées.",
                 "nl": "{n} transactie(s) over gezondheid of overtuigingen werden uitgesloten en worden nooit geanalyseerd."},
    "fraud_basis": {"fr": "Base légale : prévention de la fraude (non désactivable).",
                    "nl": "Rechtsgrond: fraudepreventie (niet uit te schakelen)."},
    "consent_basis": {"fr": "Basé sur les données que vous avez autorisées. Vous pouvez les couper à tout moment.",
                      "nl": "Gebaseerd op de gegevens die u toestond. U kunt ze op elk moment uitschakelen."},
    "credit_human": {"fr": "Aucune décision de crédit n'est automatique : une personne l'examine toujours.",
                     "nl": "Geen enkele kredietbeslissing is automatisch: een mens bekijkt ze altijd."},
    "voice_intro": {"fr": "Message vocal de votre banque", "nl": "Spraakbericht van uw bank"},
    "human_title": {"fr": "Un conseiller pour en parler", "nl": "Een adviseur om erover te praten"},
    "human_body": {"fr": "Ce sujet mérite une vraie conversation. Choisissez un moment qui vous convient.",
                   "nl": "Dit onderwerp verdient een echt gesprek. Kies een moment dat u past."},
}


def _t(key: str, lang: str, **kw) -> str:
    text = UI_TEXT[key].get(lang) or UI_TEXT[key]["fr"]
    return text.format(**kw) if kw else text


def _cache_key(action_id: str, segment: str, lang: str, variant: str, channel: str) -> str:
    return "|".join([RENDER_VERSION, action_id, segment, lang, variant, "voice" if channel == "voice" else "screen"])


def get_copy(conn: sqlite3.Connection, decision: Decision, segment: str, lang: str, variant: str,
             now: datetime) -> tuple[dict, str]:
    """Retourne (texte, source) avec source ∈ {cache, llm, template}."""
    key = _cache_key(decision.action_id, segment, lang, variant, decision.channel)
    row = conn.execute("SELECT screen_json, source FROM render_cache WHERE cache_key = ?", (key,)).fetchone()
    if row:
        conn.execute("UPDATE render_cache SET hits = hits + 1 WHERE cache_key = ?", (key,))
        return json.loads(row["screen_json"]), f"cache:{row['source']}"
    reference = template_copy(decision.action_id, lang, variant)
    copy, source = None, "template"
    if decision.action is not None:
        prompt = llm.build_prompt(decision.action_id, decision.family, decision.action.moment, lang, variant,
                                  age_band(segment), decision.channel, reference)
        generated = llm.generate_copy(prompt)
        if generated is not None:
            copy, source = generated.model_dump(), "llm"
    if copy is None:
        copy = reference
    conn.execute("INSERT OR REPLACE INTO render_cache(cache_key, screen_json, source, created_at) VALUES (?, ?, ?, ?)",
                 (key, json.dumps(copy, ensure_ascii=False), source, now.isoformat()))
    return copy, source


def _why_panel(decision: Decision, snap: Snapshot, lang: str) -> dict:
    signals_used: list[str] = []
    families: list[str] = []
    basis = "consent"
    if decision.signal is not None:
        signals_used = [EVIDENCE_TEXT[e].get(lang, EVIDENCE_TEXT[e]["fr"]) for e in decision.signal.evidence if e in EVIDENCE_TEXT]
        families = [f for f in decision.signal.families if f in CONSENT_FAMILIES]
        basis = decision.action.legal_basis if decision.action else "consent"
    notes = [_t("fraud_basis" if basis == "fraud_prevention" else "consent_basis", lang)]
    if decision.requires_human:
        notes.append(_t("credit_human", lang))
    if decision.abstain_reason:
        notes.insert(0, ABSTAIN_REASON_TEXT[decision.abstain_reason].get(lang, ABSTAIN_REASON_TEXT[decision.abstain_reason]["fr"]))
    if snap.excluded_sensitive:
        notes.append(_t("excluded", lang, n=snap.excluded_sensitive))
    return {"type": "why_panel", "title": _t("why_title", lang), "signals_used": signals_used,
            "families": families, "legal_basis": basis, "notes": notes}


def build_screen(conn: sqlite3.Connection, decision: Decision, snap: Snapshot, segment: str, variant: str,
                 now: datetime) -> tuple[dict, str]:
    lang = snap.language if snap.language in ("fr", "nl") else "fr"
    copy, source = get_copy(conn, decision, segment, lang, variant, now)
    title = copy["title"].replace("{first_name}", snap.first_name)
    body = copy["body"].replace("{first_name}", snap.first_name)
    blocks: list[dict] = []

    if decision.action is None:
        blocks.append({"type": "abstain", "title": title, "body": body})
    else:
        action = get_action(decision.action_id)
        ctas = [{"id": c.id, "label": c.label.get(lang, c.label["fr"])} for c in action.ctas]
        if decision.action_id == "scam_pause" and snap.pending_transfer:
            pt = snap.pending_transfer
            blocks.append({"type": "transfer_hold", "amount": pt["amount"], "beneficiary": pt["beneficiary"],
                           "status": pt["status"], "hold_until": pt["hold_until"]})
        if decision.channel == "voice":
            blocks.append({"type": "voice", "title": _t("voice_intro", lang), "script": f"{title}. {body}"})
        blocks.append({"type": "highlight", "title": title, "body": body, "ctas": ctas})
        if copy.get("checklist"):
            blocks.append({"type": "checklist", "title": copy.get("checklist_title", ""), "items": copy["checklist"]})
        if decision.channel == "human":
            blocks.append({"type": "human", "title": _t("human_title", lang), "body": _t("human_body", lang)})
    blocks.append(_why_panel(decision, snap, lang))
    screen = {
        "action_id": decision.action_id,
        "family": decision.family,
        "family_label": FAMILIES[decision.family],
        "channel": decision.channel,
        "language": lang,
        "tone": variant,
        "blocks": blocks,
    }
    return screen, source
