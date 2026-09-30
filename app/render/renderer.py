"""Stage 4: turn the decision into a screen.

1. Text: cache (action x segment x language x tone x format) -> otherwise validated LLM -> otherwise template.
   Cached text is generic ({first_name} template): it is reused for the whole segment.
2. Structure: assembled by the server from known block types.
3. Delivery: how the message reaches the customer (app card, push notification, voice call, advisor).
4. "Why am I seeing this" panel: built from the engine journal, never by the LLM.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.engine.catalog import get_action
from app.engine.decision import Decision
from app.engine.features import CONSENT_FAMILIES, Snapshot
from app.engine.feedback import age_band
from app.i18n import ABSTAIN_REASON, EVIDENCE, UI, norm_lang, pick
from app.render import llm
from app.render.templates import template_copy

RENDER_VERSION = "v2"


def _t(key: str, lang: str, **kw) -> str:
    text = pick(UI[key], lang)
    return text.format(**kw) if kw else text


def _cache_key(action_id: str, segment: str, lang: str, variant: str, channel: str) -> str:
    return "|".join([RENDER_VERSION, action_id, segment, lang, variant, "voice" if channel == "voice" else "screen"])


def get_copy(conn: sqlite3.Connection, decision: Decision, segment: str, lang: str, variant: str,
             now: datetime) -> tuple[dict, str]:
    """Return (text, source) with source in {cache:..., llm, template}."""
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
            copy["push"] = copy.get("push") or reference["push"]
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
        signals_used = [pick(EVIDENCE[e], lang) for e in decision.signal.evidence if e in EVIDENCE]
        families = [f for f in decision.signal.families if f in CONSENT_FAMILIES]
        basis = decision.action.legal_basis if decision.action else "consent"
    notes = [_t("fraud_basis" if basis == "fraud_prevention" else "consent_basis", lang)]
    if decision.requires_human:
        notes.append(_t("credit_human", lang))
    if decision.abstain_reason:
        notes.insert(0, pick(ABSTAIN_REASON[decision.abstain_reason], lang))
    if snap.excluded_sensitive:
        notes.append(_t("excluded", lang, n=snap.excluded_sensitive))
    return {"type": "why_panel", "title": _t("why_title", lang), "signals_used": signals_used,
            "families": families, "legal_basis": basis, "notes": notes}


def build_screen(conn: sqlite3.Connection, decision: Decision, snap: Snapshot, segment: str, variant: str,
                 now: datetime) -> tuple[dict, str]:
    lang = norm_lang(snap.language)
    copy, source = get_copy(conn, decision, segment, lang, variant, now)
    fill = lambda s: s.replace("{first_name}", snap.first_name)  # noqa: E731
    title, body, push = fill(copy["title"]), fill(copy["body"]), fill(copy.get("push", ""))
    blocks: list[dict] = []
    bookable = False

    if decision.action is None:
        blocks.append({"type": "abstain", "title": title, "body": body})
    else:
        action = get_action(decision.action_id)
        bookable = action.bookable
        ctas = [{"id": c.id, "label": c.label.get(lang, c.label["en"]), "effect": c.effect} for c in action.ctas]
        if decision.action_id == "scam_pause" and snap.pending_transfer:
            pt = snap.pending_transfer
            blocks.append({"type": "transfer_hold", "amount": pt["amount"], "beneficiary": pt["beneficiary"],
                           "status": pt["status"], "hold_until": pt["hold_until"]})
        blocks.append({"type": "highlight", "title": title, "body": body, "ctas": ctas})
        if copy.get("checklist"):
            blocks.append({"type": "checklist", "title": copy.get("checklist_title", ""), "items": copy["checklist"]})
        if decision.channel == "human":
            blocks.append({"type": "human", "title": _t("human_title", lang), "body": _t("human_body", lang)})
    blocks.append(_why_panel(decision, snap, lang))

    # How the message is delivered. The front end draws a different phone screen for each channel.
    delivery: dict = {"channel": decision.channel}
    if decision.channel == "push":
        delivery.update(title=title, text=push or body[:100])
    elif decision.channel == "voice":
        delivery.update(title=title, text=f"{title}. {body}")
    screen = {
        "action_id": decision.action_id,
        "family": decision.family,
        "channel": decision.channel,
        "language": lang,
        "tone": variant,
        "bookable": bookable,
        "delivery": delivery,
        "blocks": blocks,
    }
    return screen, source
