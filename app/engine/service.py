"""Orchestration of the full pipeline for one customer: signals -> decision -> rendering -> journal -> feedback,
plus the customer-side business actions (buttons, scam pause, consent, language, appointments)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from app.config import LANGUAGES
from app.engine import feedback as fb
from app.engine import hitl
from app.engine.catalog import cta_for, get_action
from app.engine.decision import Context, decide
from app.engine.features import CONSENT_FAMILIES, build_snapshot, load_consents
from app.engine.hitl import Conflict, NotFound
from app.engine.signals import derive
from app.i18n import MESSAGES, norm_lang, pick
from app.render.renderer import build_screen

SCAM_HOLD_MINUTES = 10

__all__ = ["NotFound", "Conflict", "compute_feed", "handle_cta", "handle_feedback", "owned_decision",
           "get_consents", "set_consent", "set_language", "book_for_customer", "cancel_for_customer"]


def wall_clock() -> datetime:
    """Real clock, used for the scam pause (the rest of the demo follows DEMO_NOW)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _customer(conn: sqlite3.Connection, customer_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        raise NotFound()
    return row


def _recent_proactive(conn: sqlite3.Connection, customer_id: str, now: datetime) -> set[str]:
    since = (now - timedelta(days=7)).isoformat()
    return {r["action_id"] for r in conn.execute(
        "SELECT DISTINCT action_id FROM decisions WHERE customer_id = ? AND channel IN ('push','voice') AND created_at >= ?",
        (customer_id, since),
    )}


def compute_feed(conn: sqlite3.Connection, customer_id: str, now: datetime) -> dict:
    cust = _customer(conn, customer_id)
    snap = build_snapshot(conn, customer_id, now)
    sig = derive(snap, now.month)
    ref = fb.customer_ref(conn, customer_id)
    segment = fb.segment_of(cust["age"], cust["household"])
    proactive = _recent_proactive(conn, customer_id, now)

    ctx = Context(
        now=now,
        efficiency=lambda a: fb.efficiency(conn, a, segment, now),
        suppressed=lambda a: fb.is_suppressed(conn, ref, a, now),
        recent_proactive=False,
    )
    decision = decide(snap, sig, ctx)
    # Frequency cap: a proactive nudge for ANOTHER action in the last 7 days
    if decision.action and (proactive - {decision.action_id}):
        ctx.recent_proactive = True
        decision = decide(snap, sig, ctx)

    # Idempotency: the same action within 24 h reuses the same decision (same tone, same id)
    previous = conn.execute(
        "SELECT id, variant FROM decisions WHERE customer_id = ? AND action_id = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
        (customer_id, decision.action_id, (now - timedelta(hours=24)).isoformat()),
    ).fetchone()
    variant_info: dict = {}
    if previous:
        decision_id, variant = previous["id"], previous["variant"]
    else:
        decision_id = uuid.uuid4().hex
        if decision.action:
            variant, variant_info = fb.choose_variant(conn, decision.action_id, segment, decision.action.variants, now)
        else:
            variant = "direct"

    # Scam pause: the transfer is put on hold, real clock, enforced on the server
    hold_started = False
    if decision.action_id == "scam_pause" and snap.pending_transfer and snap.pending_transfer["status"] == "pending":
        hold_until = (wall_clock() + timedelta(minutes=SCAM_HOLD_MINUTES)).isoformat()
        conn.execute("UPDATE pending_transfers SET status = 'held', hold_until = ? WHERE id = ?",
                     (hold_until, snap.pending_transfer["id"]))
        snap.pending_transfer = {**snap.pending_transfer, "status": "held", "hold_until": hold_until}
        hold_started = True

    screen, render_source = build_screen(conn, decision, snap, segment, variant, now)
    journal = {
        "computed_at": now.isoformat(),
        "segment": segment,
        "consents": snap.consents,
        "excluded_sensitive_transactions": snap.excluded_sensitive,
        "derived": sig.to_dict(),
        "candidates": [c.to_dict() for c in sorted(decision.candidates, key=lambda c: -c.score)],
        "guardrails": list(dict.fromkeys(decision.guardrails)),
        "decision": {
            "action_id": decision.action_id, "family": decision.family, "score": round(decision.score, 3),
            "channel": decision.channel, "channel_reason": decision.channel_reason,
            "requires_human": decision.requires_human, "abstain_reason": decision.abstain_reason,
        },
        "render": {"source": render_source, "variant": variant, "bandit": variant_info, "language": screen["language"]},
    }

    if previous:
        conn.execute("UPDATE decisions SET journal_json = ?, screen_json = ?, score = ?, channel = ? WHERE id = ?",
                     (json.dumps(journal, ensure_ascii=False), json.dumps(screen, ensure_ascii=False),
                      decision.score, decision.channel, decision_id))
    else:
        conn.execute(
            "INSERT INTO decisions(id, customer_id, created_at, action_id, action_family, channel, score, variant, journal_json, screen_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (decision_id, customer_id, now.isoformat(), decision.action_id, decision.family, decision.channel,
             decision.score, variant, json.dumps(journal, ensure_ascii=False), json.dumps(screen, ensure_ascii=False)),
        )
        if decision.action:
            fb.record_sent(conn, decision_id, ref, decision.action_id, segment, decision.channel, variant, now)
            fb.record_reaction(conn, decision_id, "seen", now)
            # The engine proposes, a person decides: sensitive topics go to the advisor queue
            if decision.channel == "human":
                task_type = "fraud_review" if decision.action.family == "protect" else "outreach"
                reason = "crypto_verification" if task_type == "fraud_review" else "engine_outreach"
                hitl.open_task(conn, customer_id, decision_id, decision.action_id, task_type, reason, now)
    if hold_started:
        hitl.open_task(conn, customer_id, decision_id, "scam_pause", "fraud_review", "fraud_hold", now, priority="high")

    appointments = [a for a in hitl.customer_appointments(conn, customer_id) if a["status"] == "booked"]
    return {"decision_id": decision_id, "screen": screen, "journal": journal,
            "active_appointment": appointments[0] if appointments else None}


def owned_decision(conn: sqlite3.Connection, customer_id: str, decision_id: str) -> sqlite3.Row:
    """Central IDOR check: a decision is only reachable by its owner."""
    row = conn.execute("SELECT * FROM decisions WHERE id = ? AND customer_id = ?", (decision_id, customer_id)).fetchone()
    if row is None:
        raise NotFound()
    return row


def _msg(key: str, lang: str) -> str:
    return pick(MESSAGES[key], norm_lang(lang))


def handle_cta(conn: sqlite3.Connection, customer_id: str, decision_id: str, cta_id: str, now: datetime) -> dict:
    row = owned_decision(conn, customer_id, decision_id)
    cta = cta_for(row["action_id"], cta_id)          # server-side validation: the button must exist for THIS action
    if cta is None:
        raise NotFound()
    lang = _customer(conn, customer_id)["language"]
    effect = cta.effect
    if effect in ("cancel_transfer", "confirm_transfer"):
        pt = conn.execute(
            "SELECT * FROM pending_transfers WHERE customer_id = ? AND status = 'held' ORDER BY id DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        if pt is None:
            raise Conflict("No transfer is waiting.")
        task = conn.execute("SELECT id FROM advisor_tasks WHERE customer_id = ? AND task_type = 'fraud_review' AND status = 'open'",
                            (customer_id,)).fetchone()
        if effect == "confirm_transfer":
            remaining = (datetime.fromisoformat(pt["hold_until"]) - wall_clock()).total_seconds()
            if remaining > 0:
                raise Conflict(f"Safety pause in progress: {int(remaining // 60) + 1} more minute(s).")
            conn.execute("UPDATE pending_transfers SET status = 'confirmed' WHERE id = ?", (pt["id"],))
            fb.record_reaction(conn, decision_id, "clicked", now)
            if task:
                hitl.close_task(conn, task["id"], "customer", "customer_confirmed", "", now)
        else:
            conn.execute("UPDATE pending_transfers SET status = 'cancelled' WHERE id = ?", (pt["id"],))
            fb.record_reaction(conn, decision_id, "completed", now)
            if task:
                hitl.close_task(conn, task["id"], "customer", "customer_cancelled", "", now)
    elif effect == "callback":
        hitl.open_task(conn, customer_id, decision_id, row["action_id"], "callback", "customer_callback", now, actor="customer")
        fb.record_reaction(conn, decision_id, "completed", now)
    elif effect == "fraud_call":
        hitl.open_task(conn, customer_id, decision_id, row["action_id"], "fraud_review", "customer_fraud_call", now,
                       actor="customer", priority="high")
        fb.record_reaction(conn, decision_id, "completed", now)
    elif effect == "book":
        fb.record_reaction(conn, decision_id, "clicked", now)   # completed once the booking is actually made
    elif effect == "complete":
        fb.record_reaction(conn, decision_id, "completed", now)
    else:
        fb.record_reaction(conn, decision_id, "clicked", now)
    return {"ok": True, "effect": effect, "message": _msg(effect, lang)}


def handle_feedback(conn: sqlite3.Connection, customer_id: str, decision_id: str, reaction: str, now: datetime) -> dict:
    row = owned_decision(conn, customer_id, decision_id)
    if reaction not in fb.CLIENT_REACTIONS:
        raise Conflict("Reaction not allowed.")
    if row["action_id"] == "abstain" or get_action(row["action_id"]) is None:
        raise Conflict("Nothing to rate for an abstention.")
    fb.record_reaction(conn, decision_id, reaction, now)
    return {"ok": True}


def get_consents(conn: sqlite3.Connection, customer_id: str) -> list[dict]:
    current = load_consents(conn, customer_id)
    return [{"family": f, "enabled": current[f]} for f in CONSENT_FAMILIES]


def set_consent(conn: sqlite3.Connection, customer_id: str, family: str, enabled: bool, now: datetime) -> None:
    if family not in CONSENT_FAMILIES:
        raise NotFound()
    conn.execute(
        "INSERT INTO consents(customer_id, family, enabled, updated_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(customer_id, family) DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at",
        (customer_id, family, int(enabled), now.isoformat()),
    )


def set_language(conn: sqlite3.Connection, customer_id: str, language: str) -> None:
    if language not in LANGUAGES:
        raise NotFound()
    conn.execute("UPDATE customers SET language = ? WHERE id = ?", (language, customer_id))


def book_for_customer(conn: sqlite3.Connection, customer_id: str, decision_id: str, slot_id: int, mode: str,
                      now: datetime) -> dict:
    row = owned_decision(conn, customer_id, decision_id)
    action = get_action(row["action_id"])
    if action is None or not action.bookable:
        raise Conflict("This message does not offer an appointment.")
    hitl.book(conn, customer_id, slot_id, mode, row["action_id"], decision_id, "customer", now)
    return {"ok": True, "message": _msg("booked", _customer(conn, customer_id)["language"])}


def cancel_for_customer(conn: sqlite3.Connection, customer_id: str, appointment_id: int, now: datetime) -> dict:
    hitl.cancel_appointment(conn, appointment_id, "customer", now, customer_id=customer_id)
    return {"ok": True, "message": _msg("cancelled", _customer(conn, customer_id)["language"])}
