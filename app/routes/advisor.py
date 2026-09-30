"""Advisor endpoints: human in the loop (GDPR art. 22) and monitoring of the learning loop.

Least privilege: an advisor only sees the detailed journal of a decision when a task exists for
that customer. Metrics are aggregated and pseudonymised. Every task action is validated against
the task type and written to the audit trail.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.config import settings
from app.db import get_conn
from app.engine import hitl
from app.engine.catalog import CATALOG
from app.engine.feedback import NEGATIVE, REACTION_WEIGHTS, age_band, efficiency
from app.schemas import DECISION_ID, TaskActionIn
from app.security import Principal, require_advisor

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.get("/tasks")
def tasks(_: Principal = Depends(require_advisor)) -> list[dict]:
    with get_conn() as conn:
        return hitl.list_tasks(conn)


@router.post("/tasks/{task_id}/actions")
def task_action(body: TaskActionIn, task_id: int = Path(ge=1), p: Principal = Depends(require_advisor)) -> dict:
    try:
        with get_conn() as conn:
            hitl.advisor_action(conn, task_id, p.username, body.action, settings.demo_now, note=body.note,
                                outcome=body.outcome, slot_id=body.slot_id, mode=body.mode)
    except hitl.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    except hitl.Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return {"ok": True}


@router.get("/slots")
def slots(_: Principal = Depends(require_advisor)) -> list[dict]:
    with get_conn() as conn:
        return hitl.available_slots(conn, settings.demo_now, limit=20)


@router.get("/appointments")
def appointments(_: Principal = Depends(require_advisor)) -> list[dict]:
    with get_conn() as conn:
        return hitl.upcoming_appointments(conn, settings.demo_now)


@router.get("/decisions/{decision_id}")
def decision_journal(decision_id: str = Path(pattern=DECISION_ID), _: Principal = Depends(require_advisor)) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT d.id, d.action_id, d.channel, d.created_at, d.journal_json FROM decisions d "
            "WHERE d.id = ? AND EXISTS (SELECT 1 FROM advisor_tasks t WHERE t.customer_id = d.customer_id)",
            (decision_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return {**{k: row[k] for k in ("id", "action_id", "channel", "created_at")}, "journal": json.loads(row["journal_json"])}


@router.get("/metrics")
def metrics(_: Principal = Depends(require_advisor)) -> dict:
    now = settings.demo_now
    since = (now - timedelta(days=30)).isoformat()
    with get_conn() as conn:
        events = [dict(r) for r in conn.execute("SELECT * FROM action_events WHERE sent_at >= ?", (since,))]
        per_action: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for e in events:
            per_action[(e["action_id"], e["segment"])].append(e)
        actions = []
        for (action_id, segment), evs in sorted(per_action.items()):
            n = len(evs)
            eff, _n = efficiency(conn, action_id, segment, now)
            actions.append({
                "action_id": action_id, "family": CATALOG[action_id].family, "segment": segment, "sent": n,
                "efficiency": round(eff, 3),
                "completion_rate": round(sum(e["reaction"] == "completed" for e in evs) / n, 3),
                "refusal_rate": round(sum(e["reaction"] in NEGATIVE for e in evs) / n, 3),
                "why_opened_rate": round(sum(e["why_opened"] for e in evs) / n, 3),
            })
        # Bandit: successes / failures per tone variant
        bandit: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"successes": 0, "failures": 0}))
        for e in events:
            k = "successes" if e["reaction"] in ("clicked", "completed") else "failures"
            bandit[e["action_id"]][e["variant"]][k] += 1
        # Fairness: commercial pressure and refusals per age band
        by_band: dict[str, dict[str, int]] = defaultdict(lambda: {"sent": 0, "commercial": 0, "refused": 0})
        for e in events:
            b = by_band[age_band(e["segment"])]
            b["sent"] += 1
            b["commercial"] += int(CATALOG[e["action_id"]].is_commercial)
            b["refused"] += int(e["reaction"] in NEGATIVE)
        total_sent = sum(b["sent"] for b in by_band.values()) or 1
        overall_commercial = sum(b["commercial"] for b in by_band.values()) / total_sent
        fairness = []
        for band, b in sorted(by_band.items()):
            share = b["commercial"] / b["sent"] if b["sent"] else 0
            fairness.append({"age_band": band, "sent": b["sent"], "commercial_share": round(share, 3),
                             "refusal_rate": round(b["refused"] / b["sent"], 3) if b["sent"] else 0,
                             "alert": bool(overall_commercial and share > 1.5 * overall_commercial and b["sent"] >= 20)})
        # Curve: mean reaction value per day
        daily: dict[str, list[float]] = defaultdict(list)
        for e in events:
            daily[e["sent_at"][:10]].append(REACTION_WEIGHTS.get(e["reaction"], 0.0))
        timeline = [{"day": d, "mean_value": round(sum(v) / len(v), 3), "sent": len(v)} for d, v in sorted(daily.items())]
        channels: dict[str, int] = defaultdict(int)
        for e in events:
            channels[e["channel"]] += 1
        cache = conn.execute("SELECT COUNT(*) AS entries, COALESCE(SUM(hits),0) AS hits, "
                             "COALESCE(SUM(source='llm'),0) AS llm FROM render_cache").fetchone()
        open_tasks = conn.execute("SELECT COUNT(*) FROM advisor_tasks WHERE status = 'open'").fetchone()[0]
        upcoming = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'booked'").fetchone()[0]
        abstentions = conn.execute("SELECT COUNT(*) FROM decisions WHERE action_id = 'abstain' AND created_at >= ?", (since,)).fetchone()[0]
    renders = cache["entries"] + cache["hits"]
    return {
        "window_days": 30,
        "totals": {"sent": len(events), "abstentions": abstentions, "open_tasks": open_tasks, "appointments": upcoming,
                   "completion_rate": round(sum(e["reaction"] == "completed" for e in events) / (len(events) or 1), 3),
                   "refusal_rate": round(sum(e["reaction"] in NEGATIVE for e in events) / (len(events) or 1), 3)},
        "actions": actions,
        "channels": dict(channels),
        "bandit": {a: dict(v) for a, v in bandit.items()},
        "fairness": fairness,
        "timeline": timeline,
        "render_cache": {"entries": cache["entries"], "hits": cache["hits"], "llm_entries": cache["llm"],
                         "hit_rate": round(cache["hits"] / renders, 3) if renders else 0.0},
    }
