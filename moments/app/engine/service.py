"""Orchestration du pipeline complet pour un client : signaux -> décision -> rendu -> journal -> feedback."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from app.engine import feedback as fb
from app.engine.catalog import cta_for, get_action
from app.engine.decision import GUARDRAIL_TEXT, Context, decide
from app.engine.features import CONSENT_FAMILIES, build_snapshot
from app.engine.signals import derive
from app.render.renderer import build_screen

SCAM_HOLD_MINUTES = 10


class NotFound(Exception):
    """Levée aussi quand la ressource existe mais appartient à un autre client (pas de fuite d'existence)."""


class Conflict(Exception):
    pass


def wall_clock() -> datetime:
    """Horloge réelle, utilisée pour la pause anti-arnaque (le reste de la démo suit DEMO_NOW)."""
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
    # Plafond de fréquence : un nudge proactif pour une AUTRE action dans les 7 derniers jours
    if decision.action and (proactive - {decision.action_id}):
        ctx.recent_proactive = True
        decision = decide(snap, sig, ctx)

    # Idempotence : la même action dans les dernières 24 h réutilise la même décision (même variante, même id)
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

    # Pause anti-arnaque : le virement est mis en attente, horloge réelle, appliquée côté serveur
    if decision.action_id == "scam_pause" and snap.pending_transfer and snap.pending_transfer["status"] == "pending":
        hold_until = (wall_clock() + timedelta(minutes=SCAM_HOLD_MINUTES)).isoformat()
        conn.execute("UPDATE pending_transfers SET status = 'held', hold_until = ? WHERE id = ?",
                     (hold_until, snap.pending_transfer["id"]))
        snap.pending_transfer = {**snap.pending_transfer, "status": "held", "hold_until": hold_until}

    screen, render_source = build_screen(conn, decision, snap, segment, variant, now)
    journal = {
        "computed_at": now.isoformat(),
        "segment": segment,
        "consents": snap.consents,
        "excluded_sensitive_transactions": snap.excluded_sensitive,
        "derived": sig.to_dict(),
        "candidates": [c.to_dict() for c in sorted(decision.candidates, key=lambda c: -c.score)],
        "guardrails": [{"code": g, "text": GUARDRAIL_TEXT.get(g, g)} for g in dict.fromkeys(decision.guardrails)],
        "decision": {
            "action_id": decision.action_id, "family": decision.family, "score": round(decision.score, 3),
            "channel": decision.channel, "channel_reason": decision.channel_reason,
            "requires_human": decision.requires_human, "abstain_reason": decision.abstain_reason,
        },
        "render": {"source": render_source, "variant": variant, "bandit": variant_info,
                   "llm_input": "action + texte de référence + langue + ton + tranche d'âge (aucune donnée brute)"},
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
            if decision.channel == "human":
                _open_advisor_task(conn, customer_id, decision_id, decision.action_id,
                                   "Proposition proactive du moteur : un conseiller décide s'il appelle", now)
    return {"decision_id": decision_id, "screen": screen, "journal": journal}


def _open_advisor_task(conn: sqlite3.Connection, customer_id: str, decision_id: str, action_id: str,
                       reason: str, now: datetime) -> None:
    exists = conn.execute(
        "SELECT 1 FROM advisor_tasks WHERE customer_id = ? AND action_id = ? AND status = 'open'",
        (customer_id, action_id),
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO advisor_tasks(customer_id, decision_id, action_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (customer_id, decision_id, action_id, reason, now.isoformat()),
        )


def owned_decision(conn: sqlite3.Connection, customer_id: str, decision_id: str) -> sqlite3.Row:
    """Contrôle IDOR central : une décision n'est accessible qu'à son propriétaire."""
    row = conn.execute("SELECT * FROM decisions WHERE id = ? AND customer_id = ?", (decision_id, customer_id)).fetchone()
    if row is None:
        raise NotFound()
    return row


MESSAGES = {
    "complete": {"fr": "C'est fait. (Démo : l'action est simulée.)", "nl": "Klaar. (Demo: de actie is gesimuleerd.)"},
    "ack": {"fr": "Merci, nous vous en disons plus ci-dessous.", "nl": "Bedankt, hieronder leest u meer."},
    "advisor_task": {"fr": "Un conseiller vous recontacte. Aucune décision n'est prise sans vous.",
                     "nl": "Een adviseur neemt contact met u op. Er wordt niets beslist zonder u."},
    "cancel_transfer": {"fr": "Virement annulé. Votre argent n'a pas bougé.", "nl": "Overschrijving geannuleerd. Uw geld is niet verplaatst."},
    "confirm_transfer": {"fr": "Virement confirmé et exécuté.", "nl": "Overschrijving bevestigd en uitgevoerd."},
}


def handle_cta(conn: sqlite3.Connection, customer_id: str, decision_id: str, cta_id: str, now: datetime) -> dict:
    row = owned_decision(conn, customer_id, decision_id)
    cta = cta_for(row["action_id"], cta_id)          # validation serveur : le bouton doit exister pour CETTE action
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
            raise Conflict("Aucun virement en attente.")
        if effect == "confirm_transfer":
            remaining = (datetime.fromisoformat(pt["hold_until"]) - wall_clock()).total_seconds()
            if remaining > 0:
                raise Conflict(f"Pause de sécurité en cours : encore {int(remaining // 60) + 1} min.")
            conn.execute("UPDATE pending_transfers SET status = 'confirmed' WHERE id = ?", (pt["id"],))
            fb.record_reaction(conn, decision_id, "clicked", now)
        else:
            conn.execute("UPDATE pending_transfers SET status = 'cancelled' WHERE id = ?", (pt["id"],))
            fb.record_reaction(conn, decision_id, "completed", now)
    elif effect == "advisor_task":
        _open_advisor_task(conn, customer_id, decision_id, row["action_id"], f"Demande du client : {cta_id}", now)
        fb.record_reaction(conn, decision_id, "completed", now)
    elif effect == "complete":
        fb.record_reaction(conn, decision_id, "completed", now)
    else:
        fb.record_reaction(conn, decision_id, "clicked", now)
    return {"ok": True, "effect": effect, "message": MESSAGES[effect].get(lang, MESSAGES[effect]["fr"])}


def handle_feedback(conn: sqlite3.Connection, customer_id: str, decision_id: str, reaction: str, now: datetime) -> dict:
    row = owned_decision(conn, customer_id, decision_id)
    if reaction not in fb.CLIENT_REACTIONS:
        raise Conflict("Réaction non autorisée.")
    if row["action_id"] == "abstain" or get_action(row["action_id"]) is None:
        raise Conflict("Rien à évaluer pour une abstention.")
    fb.record_reaction(conn, decision_id, reaction, now)
    return {"ok": True}


def get_consents(conn: sqlite3.Connection, customer_id: str) -> list[dict]:
    from app.engine.features import load_consents
    current = load_consents(conn, customer_id)
    return [{"family": f, "label": CONSENT_FAMILIES[f], "enabled": current[f]} for f in CONSENT_FAMILIES]


def set_consent(conn: sqlite3.Connection, customer_id: str, family: str, enabled: bool, now: datetime) -> None:
    if family not in CONSENT_FAMILIES:
        raise NotFound()
    conn.execute(
        "INSERT INTO consents(customer_id, family, enabled, updated_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(customer_id, family) DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at",
        (customer_id, family, int(enabled), now.isoformat()),
    )
