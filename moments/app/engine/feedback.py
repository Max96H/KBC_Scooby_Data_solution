"""Étage 5 : boucle de feedback (annexe C).

- Chaque action envoyée est enregistrée avec la réaction du client (identifiant pseudonymisé).
- Score d'efficacité par action × segment sur 30 jours, borné pour peser au maximum 30 % du score final.
- Bandit de Thompson sur les variantes de message (ton), jamais sur les garde-fous.
"""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets
import sqlite3
from datetime import datetime, timedelta

REACTION_WEIGHTS: dict[str, float] = {
    "ignored": 0.0,
    "seen": 0.1,
    "clicked": 0.3,
    "completed": 1.0,     # action utile complétée : le vrai succès
    "not_now": -0.5,      # déclenche une pause de 30 jours
    "never": -1.0,        # l'action a franchi une limite
    "intrusive": -1.5,
}
# Réactions que le client peut envoyer lui-même (les autres sont posées par le serveur)
CLIENT_REACTIONS = {"seen", "clicked", "not_now", "never", "intrusive"}
NEGATIVE = {"not_now", "never", "intrusive"}
MIN_W, MAX_W = min(REACTION_WEIGHTS.values()), max(REACTION_WEIGHTS.values())
EFFICIENCY_PRIOR = 0.5          # sans historique : neutre
LEARNING_SHARE = 0.30           # l'apprentissage ne pèse jamais plus de 30 %
REFUSAL_PAUSE_DAYS = 30
FOREVER = "9999-12-31T00:00:00"


def _salt(conn: sqlite3.Connection) -> bytes:
    row = conn.execute("SELECT value FROM meta WHERE key = 'pseudonym_salt'").fetchone()
    if row:
        return row["value"].encode()
    value = secrets.token_hex(32)
    conn.execute("INSERT INTO meta(key, value) VALUES ('pseudonym_salt', ?)", (value,))
    return value.encode()


def customer_ref(conn: sqlite3.Connection, customer_id: str) -> str:
    """Pseudonyme stable (HMAC-SHA256 avec sel secret stocké en base, pas dans le code)."""
    return hmac.new(_salt(conn), customer_id.encode(), hashlib.sha256).hexdigest()[:24]


def segment_of(age: int, household: str) -> str:
    band = "18-25" if age <= 25 else "26-44" if age <= 44 else "45-64" if age <= 64 else "65+"
    return f"{band}/{household}"


def age_band(segment: str) -> str:
    return segment.split("/")[0]


def efficiency(conn: sqlite3.Connection, action_id: str, segment: str, now: datetime) -> tuple[float, int]:
    """Moyenne des poids de réaction sur 30 jours, ramenée sur [0, 1]."""
    since = (now - timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT reaction FROM action_events WHERE action_id = ? AND segment = ? AND sent_at >= ?",
        (action_id, segment, since),
    ).fetchall()
    if not rows:
        return EFFICIENCY_PRIOR, 0
    mean = sum(REACTION_WEIGHTS.get(r["reaction"], 0.0) for r in rows) / len(rows)
    return (mean - MIN_W) / (MAX_W - MIN_W), len(rows)


def apply_learning(score: float, eff: float) -> float:
    return score * ((1 - LEARNING_SHARE) + LEARNING_SHARE * eff)


def variant_stats(conn: sqlite3.Connection, action_id: str, segment: str, now: datetime) -> dict[str, tuple[int, int]]:
    since = (now - timedelta(days=30)).isoformat()
    stats: dict[str, list[int]] = {}
    for r in conn.execute(
        "SELECT variant, reaction FROM action_events WHERE action_id = ? AND segment = ? AND sent_at >= ?",
        (action_id, segment, since),
    ):
        s = stats.setdefault(r["variant"], [0, 0])
        if r["reaction"] in ("clicked", "completed"):
            s[0] += 1
        else:
            s[1] += 1
    return {k: (v[0], v[1]) for k, v in stats.items()}


def choose_variant(conn: sqlite3.Connection, action_id: str, segment: str, variants: tuple[str, ...],
                   now: datetime, rng: random.Random | None = None) -> tuple[str, dict]:
    """Thompson sampling : on tire dans Beta(1+succès, 1+échecs) pour chaque variante."""
    rng = rng or random.Random()
    stats = variant_stats(conn, action_id, segment, now)
    draws = {}
    for v in variants:
        succ, fail = stats.get(v, (0, 0))
        draws[v] = rng.betavariate(1 + succ, 1 + fail)
    best = max(draws, key=draws.get)
    return best, {v: {"successes": stats.get(v, (0, 0))[0], "failures": stats.get(v, (0, 0))[1],
                      "draw": round(d, 3)} for v, d in draws.items()}


def is_suppressed(conn: sqlite3.Connection, ref: str, action_id: str, now: datetime) -> str | None:
    row = conn.execute(
        "SELECT until, reason FROM suppressions WHERE customer_ref = ? AND action_id = ? AND until > ?",
        (ref, action_id, now.isoformat()),
    ).fetchone()
    return row["reason"] if row else None


def record_sent(conn: sqlite3.Connection, decision_id: str, ref: str, action_id: str, segment: str,
                channel: str, variant: str, now: datetime, simulated: bool = False) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO action_events(decision_id, customer_ref, action_id, segment, channel, variant, sent_at, simulated)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (decision_id, ref, action_id, segment, channel, variant, now.isoformat(), int(simulated)),
    )


def record_reaction(conn: sqlite3.Connection, decision_id: str, reaction: str, now: datetime) -> None:
    """Met à jour la réaction. Une réaction positive ne peut pas effacer un refus (le refus prime)."""
    if reaction not in REACTION_WEIGHTS:
        raise ValueError("reaction inconnue")
    row = conn.execute("SELECT * FROM action_events WHERE decision_id = ?", (decision_id,)).fetchone()
    if row is None:
        raise KeyError(decision_id)
    current = row["reaction"]
    if current in NEGATIVE and reaction not in NEGATIVE:
        return
    if reaction not in NEGATIVE and REACTION_WEIGHTS[reaction] < REACTION_WEIGHTS.get(current, 0):
        return  # on garde la réaction la plus forte (ex. "completed" > "seen")
    conn.execute("UPDATE action_events SET reaction = ?, reaction_at = ? WHERE decision_id = ?",
                 (reaction, now.isoformat(), decision_id))
    if reaction == "not_now":
        until = (now + timedelta(days=REFUSAL_PAUSE_DAYS)).isoformat()
        conn.execute("INSERT OR REPLACE INTO suppressions VALUES (?, ?, ?, ?)",
                     (row["customer_ref"], row["action_id"], until, "refus : pause de 30 jours"))
    elif reaction in ("never", "intrusive"):
        conn.execute("INSERT OR REPLACE INTO suppressions VALUES (?, ?, ?, ?)",
                     (row["customer_ref"], row["action_id"], FOREVER, "le client ne veut plus voir cette action"))


def mark_why_opened(conn: sqlite3.Connection, decision_id: str) -> None:
    conn.execute("UPDATE action_events SET why_opened = 1 WHERE decision_id = ?", (decision_id,))
