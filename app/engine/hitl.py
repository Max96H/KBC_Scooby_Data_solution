"""Human in the loop: advisor tasks, appointments and the actions an advisor can take.

Principles
- The engine proposes, a person decides: sensitive topics, credit and fraud checks always end up here.
- Every task has a TYPE, and each type has its own allowed actions (validated on the server).
- Everything that happens on a task is written to an audit trail (task_events).
- Business rules are enforced on the server AND, for double bookings, by the database itself.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.engine import feedback as fb
from app.engine.catalog import get_action


class NotFound(Exception):
    """Also raised when the resource exists but belongs to someone else (no existence leak)."""


class Conflict(Exception):
    pass


TASK_TYPES = ("outreach", "callback", "appointment", "credit_review", "fraud_review")

# The only actions an advisor can take, per task type
TASK_ACTIONS: dict[str, tuple[str, ...]] = {
    "outreach": ("log_call", "book_appointment", "dismiss"),
    "callback": ("log_call", "book_appointment", "dismiss"),
    "appointment": ("complete", "no_show", "cancel_appointment"),
    "credit_review": ("complete", "no_show", "cancel_appointment"),
    "fraud_review": ("release_transfer", "block_transfer", "log_call"),
}
ACTIONS_NEEDING_NOTE = {"dismiss", "complete", "release_transfer"}
CALL_OUTCOMES = ("reached", "no_answer")
MODES = ("phone", "video", "branch")


# --------------------------------------------------------------------------- tasks
def log_event(conn: sqlite3.Connection, task_id: int, actor: str, event: str, now: datetime, detail: str = "") -> None:
    conn.execute("INSERT INTO task_events(task_id, at, actor, event, detail) VALUES (?, ?, ?, ?, ?)",
                 (task_id, now.isoformat(), actor, event, detail[:500]))


def open_task(conn: sqlite3.Connection, customer_id: str, decision_id: str | None, action_id: str, task_type: str,
              reason_code: str, now: datetime, actor: str = "engine", priority: str = "normal") -> int:
    """Create a task, or return the open one of the same type for this customer and action (no duplicates)."""
    assert task_type in TASK_TYPES
    row = conn.execute(
        "SELECT id, priority FROM advisor_tasks WHERE customer_id = ? AND action_id = ? AND task_type = ? AND status = 'open'",
        (customer_id, action_id, task_type),
    ).fetchone()
    if row:
        if priority == "high" and row["priority"] != "high":
            conn.execute("UPDATE advisor_tasks SET priority = 'high' WHERE id = ?", (row["id"],))
        log_event(conn, row["id"], actor, reason_code, now)
        return row["id"]
    cur = conn.execute(
        "INSERT INTO advisor_tasks(customer_id, decision_id, action_id, task_type, priority, reason_code, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (customer_id, decision_id, action_id, task_type, priority, reason_code, now.isoformat()),
    )
    log_event(conn, cur.lastrowid, actor, "created", now, reason_code)
    return cur.lastrowid


def close_task(conn: sqlite3.Connection, task_id: int, actor: str, outcome: str, note: str, now: datetime) -> None:
    conn.execute(
        "UPDATE advisor_tasks SET status = 'done', outcome = ?, outcome_note = ?, resolved_at = ?, resolved_by = ?"
        " WHERE id = ? AND status = 'open'",
        (outcome, note[:500], now.isoformat(), actor, task_id),
    )
    log_event(conn, task_id, actor, f"closed:{outcome}", now, note)


def _reward(conn: sqlite3.Connection, decision_id: str | None, now: datetime) -> None:
    """A task that ends well is the best possible feedback for the action that created it."""
    if not decision_id:
        return
    try:
        fb.record_reaction(conn, decision_id, "completed", now)
    except KeyError:
        pass


# --------------------------------------------------------------------------- appointments
def available_slots(conn: sqlite3.Connection, now: datetime, limit: int = 12) -> list[dict]:
    rows = conn.execute(
        "SELECT s.id, s.starts_at, s.advisor FROM appointment_slots s WHERE s.starts_at > ?"
        " AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.slot_id = s.id AND a.status = 'booked')"
        " ORDER BY s.starts_at LIMIT ?",
        (now.isoformat(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _task_type_for(action_id: str) -> str:
    action = get_action(action_id)
    return "credit_review" if action and action.involves_credit else "appointment"


def book(conn: sqlite3.Connection, customer_id: str, slot_id: int, mode: str, action_id: str,
         decision_id: str | None, created_by: str, now: datetime, task_id: int | None = None) -> int:
    if mode not in MODES:
        raise Conflict("Unknown appointment mode.")
    slot = conn.execute("SELECT id, starts_at FROM appointment_slots WHERE id = ?", (slot_id,)).fetchone()
    if slot is None:
        raise NotFound()
    if slot["starts_at"] <= now.isoformat():
        raise Conflict("This time slot is in the past.")
    active = conn.execute("SELECT 1 FROM appointments WHERE customer_id = ? AND status = 'booked'", (customer_id,)).fetchone()
    if active:
        raise Conflict("You already have an upcoming appointment. Cancel it first to book another one.")
    try:
        cur = conn.execute(
            "INSERT INTO appointments(customer_id, slot_id, decision_id, action_id, mode, created_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (customer_id, slot_id, decision_id, action_id, mode, now.isoformat(), created_by),
        )
    except sqlite3.IntegrityError:
        raise Conflict("This time slot was just taken. Please pick another one.")
    appt_id = cur.lastrowid

    new_type = _task_type_for(action_id)
    if task_id is None:
        # Convert an open outreach / callback task for the same action, otherwise create a new one
        row = conn.execute(
            "SELECT id FROM advisor_tasks WHERE customer_id = ? AND action_id = ? AND status = 'open'"
            " AND task_type IN ('outreach', 'callback') ORDER BY id LIMIT 1",
            (customer_id, action_id),
        ).fetchone()
        task_id = row["id"] if row else None
    if task_id is None:
        task_id = open_task(conn, customer_id, decision_id, action_id, new_type, "customer_booking", now, actor=created_by)
    else:
        conn.execute("UPDATE advisor_tasks SET task_type = ? WHERE id = ?", (new_type, task_id))
    conn.execute("UPDATE appointments SET task_id = ? WHERE id = ?", (task_id, appt_id))
    log_event(conn, task_id, created_by, "appointment_booked", now, f"{slot['starts_at']} ({mode})")
    _reward(conn, decision_id, now)
    return appt_id


def cancel_appointment(conn: sqlite3.Connection, appt_id: int, actor: str, now: datetime,
                       customer_id: str | None = None, status: str = "cancelled", note: str = "") -> None:
    sql = "SELECT * FROM appointments WHERE id = ?"
    params: tuple = (appt_id,)
    if customer_id is not None:                          # a customer can only touch their own appointment
        sql += " AND customer_id = ?"
        params = (appt_id, customer_id)
    appt = conn.execute(sql, params).fetchone()
    if appt is None:
        raise NotFound()
    if appt["status"] != "booked":
        raise Conflict("This appointment is no longer active.")
    conn.execute("UPDATE appointments SET status = ?, note = ? WHERE id = ?", (status, note[:500], appt_id))
    if appt["task_id"]:
        close_task(conn, appt["task_id"], actor, status if customer_id is None else "cancelled_by_customer", note, now)


def customer_appointments(conn: sqlite3.Connection, customer_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT a.id, a.action_id, a.mode, a.status, a.created_by, s.starts_at, s.advisor FROM appointments a"
        " JOIN appointment_slots s ON s.id = a.slot_id WHERE a.customer_id = ?"
        " ORDER BY a.status = 'booked' DESC, s.starts_at",
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- advisor actions
def _task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM advisor_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise NotFound()
    return row


def _task_appointment(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM appointments WHERE task_id = ? AND status = 'booked'", (task_id,)).fetchone()


def _held_transfer(conn: sqlite3.Connection, customer_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM pending_transfers WHERE customer_id = ? AND status IN ('pending', 'held') ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()


def advisor_action(conn: sqlite3.Connection, task_id: int, advisor: str, action: str, now: datetime,
                   note: str = "", outcome: str | None = None, slot_id: int | None = None, mode: str | None = None) -> None:
    task = _task(conn, task_id)
    if task["status"] != "open":
        raise Conflict("This task is already closed.")
    if action not in TASK_ACTIONS[task["task_type"]]:
        raise Conflict("This action is not available for this type of task.")
    if action in ACTIONS_NEEDING_NOTE and not note.strip():
        raise Conflict("A note is required for this action.")

    if action == "log_call":
        if outcome not in CALL_OUTCOMES:
            raise Conflict("Call outcome must be 'reached' or 'no_answer'.")
        log_event(conn, task_id, advisor, f"call:{outcome}", now, note)
        if outcome == "reached" and task["task_type"] != "fraud_review":
            close_task(conn, task_id, advisor, "reached", note, now)
            _reward(conn, task["decision_id"], now)
    elif action == "book_appointment":
        if slot_id is None or mode is None:
            raise Conflict("Pick a time slot and a mode.")
        book(conn, task["customer_id"], slot_id, mode, task["action_id"], task["decision_id"], advisor, now, task_id=task_id)
    elif action == "dismiss":
        close_task(conn, task_id, advisor, "dismissed", note, now)
    elif action in ("complete", "no_show", "cancel_appointment"):
        appt = _task_appointment(conn, task_id)
        if appt is None:
            raise Conflict("No active appointment is linked to this task.")
        status = {"complete": "completed", "no_show": "no_show", "cancel_appointment": "cancelled"}[action]
        cancel_appointment(conn, appt["id"], advisor, now, status=status, note=note)
        if action == "complete":
            _reward(conn, task["decision_id"], now)
    elif action in ("release_transfer", "block_transfer"):
        pt = _held_transfer(conn, task["customer_id"])
        if pt is None:
            raise Conflict("There is no pending transfer to review for this customer.")
        new_status = "confirmed" if action == "release_transfer" else "cancelled"
        conn.execute("UPDATE pending_transfers SET status = ? WHERE id = ?", (new_status, pt["id"]))
        close_task(conn, task_id, advisor, "released" if action == "release_transfer" else "blocked", note, now)
        if action == "block_transfer":
            _reward(conn, task["decision_id"], now)


def list_tasks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT t.*, c.display_name, c.language, c.persona, u.username FROM advisor_tasks t JOIN customers c ON c.id = t.customer_id"
        " LEFT JOIN users u ON u.customer_id = t.customer_id"
        " ORDER BY t.status = 'done', t.priority = 'normal', t.created_at DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["allowed_actions"] = list(TASK_ACTIONS[r["task_type"]]) if r["status"] == "open" else []
        appt = conn.execute(
            "SELECT a.id, a.mode, a.status, s.starts_at FROM appointments a JOIN appointment_slots s ON s.id = a.slot_id"
            " WHERE a.task_id = ? ORDER BY a.id DESC LIMIT 1", (r["id"],)).fetchone()
        d["appointment"] = dict(appt) if appt else None
        if r["task_type"] == "fraud_review":
            pt = conn.execute("SELECT amount, beneficiary, status, hold_until FROM pending_transfers WHERE customer_id = ?"
                              " ORDER BY id DESC LIMIT 1", (r["customer_id"],)).fetchone()
            d["transfer"] = dict(pt) if pt else None
        d["events"] = [dict(e) for e in conn.execute(
            "SELECT at, actor, event, detail FROM task_events WHERE task_id = ? ORDER BY id", (r["id"],))]
        out.append(d)
    return out


def upcoming_appointments(conn: sqlite3.Connection, now: datetime) -> list[dict]:
    rows = conn.execute(
        "SELECT a.id, a.action_id, a.mode, a.status, a.task_id, s.starts_at, c.display_name FROM appointments a"
        " JOIN appointment_slots s ON s.id = a.slot_id JOIN customers c ON c.id = a.customer_id"
        " WHERE a.status = 'booked' AND s.starts_at > ? ORDER BY s.starts_at", (now.isoformat(),)).fetchall()
    return [dict(r) for r in rows]
