"""Customer endpoints. No endpoint takes a customer_id: it always comes from the token (anti-IDOR)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.config import settings
from app.db import get_conn
from app.engine import feedback as fb
from app.engine import hitl, service
from app.schemas import DECISION_ID, BookingIn, ConsentIn, CtaIn, FeedbackIn, LanguageIn
from app.security import Principal, require_customer
from app.voice import synthesize

router = APIRouter(prefix="/api/me", tags=["customer"])
DecisionId = Path(pattern=DECISION_ID)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, service.NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, service.Conflict):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


@router.get("")
def me(p: Principal = Depends(require_customer)) -> dict:
    with get_conn() as conn:
        c = conn.execute("SELECT display_name, first_name, language, persona, city FROM customers WHERE id = ?",
                         (p.customer_id,)).fetchone()
        balance = conn.execute(
            "SELECT (SELECT opening_balance FROM customers WHERE id = ?) + COALESCE(SUM(amount), 0) AS b "
            "FROM transactions WHERE customer_id = ? AND date <= ?",
            (p.customer_id, p.customer_id, settings.demo_now.date().isoformat()),
        ).fetchone()["b"]
    return {**dict(c), "username": p.username, "balance": round(balance, 2), "demo_now": settings.demo_now.isoformat(), "demo_mode": settings.demo_mode}


@router.put("/language")
def update_language(body: LanguageIn, p: Principal = Depends(require_customer)) -> dict:
    with get_conn() as conn:
        service.set_language(conn, p.customer_id, body.language)
    return {"ok": True, "language": body.language}


@router.get("/feed")
def feed(p: Principal = Depends(require_customer)) -> dict:
    with get_conn() as conn:
        result = service.compute_feed(conn, p.customer_id, settings.demo_now)
    if not settings.demo_mode:
        result.pop("journal", None)
    return result


@router.post("/decisions/{decision_id}/cta")
def cta(body: CtaIn, decision_id: str = DecisionId, p: Principal = Depends(require_customer)) -> dict:
    try:
        with get_conn() as conn:
            return service.handle_cta(conn, p.customer_id, decision_id, body.cta_id, settings.demo_now)
    except (service.NotFound, service.Conflict) as exc:
        raise _http(exc)


@router.post("/decisions/{decision_id}/feedback")
def feedback(body: FeedbackIn, decision_id: str = DecisionId, p: Principal = Depends(require_customer)) -> dict:
    try:
        with get_conn() as conn:
            return service.handle_feedback(conn, p.customer_id, decision_id, body.reaction, settings.demo_now)
    except (service.NotFound, service.Conflict) as exc:
        raise _http(exc)


@router.post("/decisions/{decision_id}/why")
def why_opened(decision_id: str = DecisionId, p: Principal = Depends(require_customer)) -> dict:
    try:
        with get_conn() as conn:
            service.owned_decision(conn, p.customer_id, decision_id)
            fb.mark_why_opened(conn, decision_id)
    except service.NotFound as exc:
        raise _http(exc)
    return {"ok": True}


@router.get("/decisions/{decision_id}/voice")
def voice(decision_id: str = DecisionId, p: Principal = Depends(require_customer)) -> Response:
    try:
        with get_conn() as conn:
            row = service.owned_decision(conn, p.customer_id, decision_id)
    except service.NotFound as exc:
        raise _http(exc)
    delivery = json.loads(row["screen_json"]).get("delivery", {})
    if delivery.get("channel") != "voice" or not delivery.get("text"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No voice message for this decision")
    audio = synthesize(delivery["text"])
    if audio is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)   # the front end uses the browser's voice
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/consents")
def consents(p: Principal = Depends(require_customer)) -> list[dict]:
    with get_conn() as conn:
        return service.get_consents(conn, p.customer_id)


@router.put("/consents/{family}")
def update_consent(body: ConsentIn, family: str = Path(pattern=r"^[a-z]{3,20}$"),
                   p: Principal = Depends(require_customer)) -> list[dict]:
    try:
        with get_conn() as conn:
            service.set_consent(conn, p.customer_id, family, body.enabled, settings.demo_now)
            return service.get_consents(conn, p.customer_id)
    except service.NotFound as exc:
        raise _http(exc)


# --------------------------------------------------------------------------- appointments
@router.get("/slots")
def slots(_: Principal = Depends(require_customer)) -> list[dict]:
    with get_conn() as conn:
        return hitl.available_slots(conn, settings.demo_now, limit=12)


@router.get("/appointments")
def appointments(p: Principal = Depends(require_customer)) -> list[dict]:
    with get_conn() as conn:
        return hitl.customer_appointments(conn, p.customer_id)


@router.post("/appointments")
def book(body: BookingIn, p: Principal = Depends(require_customer)) -> dict:
    try:
        with get_conn() as conn:
            return service.book_for_customer(conn, p.customer_id, body.decision_id, body.slot_id, body.mode, settings.demo_now)
    except (service.NotFound, service.Conflict) as exc:
        raise _http(exc)


@router.post("/appointments/{appointment_id}/cancel")
def cancel(appointment_id: int = Path(ge=1), p: Principal = Depends(require_customer)) -> dict:
    try:
        with get_conn() as conn:
            return service.cancel_for_customer(conn, p.customer_id, appointment_id, settings.demo_now)
    except (service.NotFound, service.Conflict) as exc:
        raise _http(exc)
