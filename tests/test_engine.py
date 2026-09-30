"""Engine tests: decisions per persona, channels, guardrails, consent, art. 9, feedback, languages,
validated LLM rendering and the human-in-the-loop flows."""
import json as _json
import random
from dataclasses import replace
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config import settings
from app.engine import feedback as fb
from app.engine import hitl
from app.engine.decision import Context, decide
from app.engine.features import build_snapshot
from app.engine.service import compute_feed, set_consent, set_language
from app.engine.signals import derive
from app.render import llm
from app.render.schema import LlmCopy

NOW = settings.demo_now

EXPECTED = {
    "c_001": ("family_insurance_review", "app"),
    "c_002": ("family_budget_support", "human"),
    "c_003": ("grandchild_savings_info", "voice"),
    "c_004": ("scam_pause", "voice"),
    "c_005": ("first_salary_budget", "app"),
    "c_006": ("abstain", "app"),
    "c_007": ("loan_simulation_resume", "app"),
    "c_008": ("overdraft_alert", "push"),
}


def _decide(conn, cid, now=NOW, **ctx):
    snap = build_snapshot(conn, cid, now)
    sig = derive(snap, now.month)
    return snap, sig, decide(snap, sig, Context(now=now, **ctx))


@pytest.mark.parametrize("cid,expected", EXPECTED.items())
def test_persona_decisions(conn, cid, expected):
    _, _, d = _decide(conn, cid)
    assert (d.action_id, d.channel) == expected


def test_every_channel_is_demonstrated():
    assert {c for _, c in EXPECTED.values()} == {"app", "push", "voice", "human"}


def test_screen_matches_channel(conn):
    push = compute_feed(conn, "c_008", NOW)["screen"]
    assert push["delivery"]["channel"] == "push" and push["delivery"]["text"] and len(push["delivery"]["text"]) <= 110
    voice = compute_feed(conn, "c_003", NOW)["screen"]
    assert voice["delivery"]["channel"] == "voice" and voice["delivery"]["text"].startswith(voice["delivery"]["title"])
    human = compute_feed(conn, "c_002", NOW)["screen"]
    assert any(b["type"] == "human" for b in human["blocks"]) and human["bookable"]
    app_ = compute_feed(conn, "c_001", NOW)["screen"]
    assert app_["delivery"] == {"channel": "app"}


def test_same_signal_opposite_decision(conn):
    """The key demo moment: same baby signal, opposite decision depending on the situation."""
    _, sig_e, d_e = _decide(conn, "c_001")
    _, sig_s, d_s = _decide(conn, "c_002")
    assert sig_e.first("life_event").value == sig_s.first("life_event").value == "baby"
    assert d_e.action.is_commercial and not d_s.action.is_commercial
    blocked = next(c for c in d_s.candidates if c.action.id == "family_insurance_review")
    assert blocked.status == "blocked" and "financial_stress_no_sales" in blocked.reasons


def test_sensitive_transactions_never_read(conn):
    snap, sig, _ = _decide(conn, "c_001")
    assert snap.excluded_sensitive == 2
    evidence = {e for s in sig.items for e in s.evidence}
    assert not any("pharm" in e or "medical" in e for e in evidence)


def test_consent_withdrawal_removes_signal_family(conn):
    set_consent(conn, "c_001", "digital", False, NOW)
    snap, sig, _ = _decide(conn, "c_001")
    assert snap.simulations == {} and "digital" not in sig.first("life_event").families
    set_consent(conn, "c_001", "transactions", False, NOW)
    _, sig, d = _decide(conn, "c_001")
    assert sig.first("life_event") is None and d.action_id == "abstain"


def test_fraud_prevention_ignores_marketing_consent(conn):
    for fam in ("transactions", "digital", "products", "profile"):
        set_consent(conn, "c_004", fam, False, NOW)
    _, _, d = _decide(conn, "c_004")
    assert d.action_id == "scam_pause"


@pytest.mark.parametrize("lang,title,why", [
    ("en", "A new family member?", "Recent purchases in baby stores"),
    ("fr", "Un nouveau membre dans la famille ?", "Achats récents dans des magasins pour bébé"),
    ("nl", "Een nieuw gezinslid?", "Recente aankopen in babywinkels"),
])
def test_content_in_three_languages(conn, lang, title, why):
    set_language(conn, "c_001", lang)
    screen = compute_feed(conn, "c_001", NOW)["screen"]
    hl = next(b for b in screen["blocks"] if b["type"] == "highlight")
    panel = next(b for b in screen["blocks"] if b["type"] == "why_panel")
    assert screen["language"] == lang and hl["title"] == title and why in panel["signals_used"]


def test_refusal_pauses_action_30_days(conn):
    feed = compute_feed(conn, "c_001", NOW)
    fb.record_reaction(conn, feed["decision_id"], "not_now", NOW)
    assert compute_feed(conn, "c_001", NOW)["screen"]["action_id"] == "abstain"
    ref = fb.customer_ref(conn, "c_001")
    assert fb.is_suppressed(conn, ref, "family_insurance_review", NOW.replace(day=20))
    assert not fb.is_suppressed(conn, ref, "family_insurance_review", datetime(2026, 11, 15))


def test_positive_reaction_cannot_erase_refusal(conn):
    feed = compute_feed(conn, "c_001", NOW)
    fb.record_reaction(conn, feed["decision_id"], "never", NOW)
    fb.record_reaction(conn, feed["decision_id"], "completed", NOW)
    r = conn.execute("SELECT reaction FROM action_events WHERE decision_id = ?", (feed["decision_id"],)).fetchone()
    assert r["reaction"] == "never"


def test_quiet_hours(conn):
    night = NOW.replace(hour=23)
    _, _, d = _decide(conn, "c_003", now=night)            # information: voice -> postponed to the app
    assert d.channel == "app" and "quiet_hours" in d.guardrails
    _, _, d = _decide(conn, "c_008", now=night)            # overdraft alert (protect): push allowed at night
    assert d.channel == "push" and "quiet_hours_overridden_for_protection" in d.guardrails


def test_frequency_cap(conn):
    _, _, d = _decide(conn, "c_003", recent_proactive=True)
    assert d.channel == "app" and "frequency_cap" in d.guardrails


def test_credit_always_human(conn):
    _, _, d = _decide(conn, "c_007")
    assert d.requires_human


def test_learning_is_bounded():
    assert fb.apply_learning(1.0, 0.0) == pytest.approx(0.7)
    assert fb.apply_learning(1.0, 1.0) == pytest.approx(1.0)


def test_thompson_prefers_better_variant(conn):
    seg = "26-44/couple"
    for i in range(60):
        for variant, success in (("warm", i % 2 == 0), ("direct", i % 10 == 0)):
            did = f"{i:04d}{variant:>28}".replace(" ", "0")[:32]
            conn.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (did, "c_001", NOW.isoformat(), "family_insurance_review", "propose", "app", 0, variant, "{}", "{}"))
            fb.record_sent(conn, did, "ref", "family_insurance_review", seg, "app", variant, NOW)
            fb.record_reaction(conn, did, "completed" if success else "ignored", NOW)
    rng = random.Random(0)
    picks = [fb.choose_variant(conn, "family_insurance_review", seg, ("warm", "direct"), NOW, rng)[0] for _ in range(200)]
    assert picks.count("warm") > 180


# ---------------------------------------------------------------- human in the loop
def _task(conn, customer_id):
    return conn.execute("SELECT * FROM advisor_tasks WHERE customer_id = ? ORDER BY id DESC", (customer_id,)).fetchone()


def test_sensitive_topic_creates_outreach_task(conn):
    compute_feed(conn, "c_002", NOW)
    t = _task(conn, "c_002")
    assert (t["task_type"], t["reason_code"], t["status"]) == ("outreach", "engine_outreach", "open")
    compute_feed(conn, "c_002", NOW)                          # no duplicate task
    assert conn.execute("SELECT COUNT(*) FROM advisor_tasks WHERE customer_id = 'c_002'").fetchone()[0] == 1


def test_customer_booking_converts_task_and_rewards_action(conn):
    feed = compute_feed(conn, "c_002", NOW)
    slot = hitl.available_slots(conn, NOW)[0]["id"]
    hitl.book(conn, "c_002", slot, "video", "family_budget_support", feed["decision_id"], "customer", NOW)
    t = _task(conn, "c_002")
    assert t["task_type"] == "appointment" and t["status"] == "open"
    reaction = conn.execute("SELECT reaction FROM action_events WHERE decision_id = ?", (feed["decision_id"],)).fetchone()[0]
    assert reaction == "completed"
    hitl.advisor_action(conn, t["id"], "advisor", "complete", NOW, note="Budget plan reviewed together")
    assert _task(conn, "c_002")["status"] == "done"
    assert conn.execute("SELECT status FROM appointments WHERE task_id = ?", (t["id"],)).fetchone()[0] == "completed"


def test_credit_booking_becomes_credit_review(conn):
    feed = compute_feed(conn, "c_007", NOW)
    slot = hitl.available_slots(conn, NOW)[0]["id"]
    hitl.book(conn, "c_007", slot, "branch", "loan_simulation_resume", feed["decision_id"], "customer", NOW)
    assert _task(conn, "c_007")["task_type"] == "credit_review"


def test_advisor_books_from_outreach_and_logs_calls(conn):
    compute_feed(conn, "c_002", NOW)
    tid = _task(conn, "c_002")["id"]
    hitl.advisor_action(conn, tid, "advisor", "log_call", NOW, outcome="no_answer")
    assert _task(conn, "c_002")["status"] == "open"                      # no answer: stays open
    slot = hitl.available_slots(conn, NOW)[0]["id"]
    hitl.advisor_action(conn, tid, "advisor", "book_appointment", NOW, slot_id=slot, mode="phone")
    t = _task(conn, "c_002")
    assert t["task_type"] == "appointment" and hitl.customer_appointments(conn, "c_002")[0]["created_by"] == "advisor"
    events = [e["event"] for e in conn.execute("SELECT event FROM task_events WHERE task_id = ?", (tid,))]
    assert events[:3] == ["created", "call:no_answer", "appointment_booked"]


def test_fraud_hold_creates_urgent_review_and_advisor_can_block(conn):
    compute_feed(conn, "c_004", NOW)
    t = _task(conn, "c_004")
    assert (t["task_type"], t["priority"], t["reason_code"]) == ("fraud_review", "high", "fraud_hold")
    with pytest.raises(hitl.Conflict):
        hitl.advisor_action(conn, t["id"], "advisor", "release_transfer", NOW)          # note required
    hitl.advisor_action(conn, t["id"], "advisor", "block_transfer", NOW, note="Customer confirms a scam call")
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id = 'c_004'").fetchone()[0] == "cancelled"
    assert _task(conn, "c_004")["outcome"] == "blocked"


def test_advisor_can_release_after_verification(conn):
    compute_feed(conn, "c_004", NOW)
    t = _task(conn, "c_004")
    hitl.advisor_action(conn, t["id"], "advisor", "release_transfer", NOW, note="Called the customer: known plumber")
    assert conn.execute("SELECT status FROM pending_transfers WHERE customer_id = 'c_004'").fetchone()[0] == "confirmed"
    with pytest.raises(hitl.Conflict):                                                   # task is closed
        hitl.advisor_action(conn, t["id"], "advisor", "block_transfer", NOW, note="x")


def test_customer_cancelling_transfer_closes_fraud_task(client):
    from tests.conftest import login
    marcel = login(client, "marcel")
    did = client.get("/api/me/feed", headers=marcel).json()["decision_id"]
    client.post(f"/api/me/decisions/{did}/cta", headers=marcel, json={"cta_id": "cancel_transfer"})
    adv = login(client, "advisor")
    task = next(x for x in client.get("/api/advisor/tasks", headers=adv).json() if x["task_type"] == "fraud_review")
    assert task["status"] == "done" and task["outcome"] == "customer_cancelled" and task["allowed_actions"] == []


def test_past_slot_cannot_be_booked(conn):
    conn.execute("INSERT INTO appointment_slots(starts_at, advisor) VALUES ('2026-09-01T09:00:00', 'advisor')")
    sid = conn.execute("SELECT id FROM appointment_slots WHERE starts_at = '2026-09-01T09:00:00'").fetchone()[0]
    with pytest.raises(hitl.Conflict):
        hitl.book(conn, "c_002", sid, "phone", "family_budget_support", None, "customer", NOW)


# ---------------------------------------------------------------- LLM rendering
@pytest.mark.parametrize("bad", [
    {"title": "Offer", "body": "<script>alert(1)</script> click quickly"},
    {"title": "Offer", "body": "Go to https://evil.example to validate"},
    {"title": "Offer", "body": "Enjoy an exceptional rate of 1.9% from today"},
    {"title": "Offer", "body": "Hello {customer_id}, here is your personal offer"},
    {"title": "Offer", "body": "A perfectly fine body text here.", "push": "Visit www.evil.example now"},
])
def test_llm_output_validation_rejects(bad):
    with pytest.raises(ValidationError):
        LlmCopy.model_validate(bad)


def test_llm_output_validation_accepts_placeholder():
    c = LlmCopy.model_validate({"title": "Hello {first_name}", "body": "A small note to help you get off to a good start."})
    assert "{first_name}" in c.title


def test_llm_path_cached_and_personalized(conn, monkeypatch):
    calls = []

    def fake(prompt):
        calls.append(prompt)
        assert "c_001" not in prompt and "Emma" not in prompt       # no identifying data sent to the LLM
        return LlmCopy(title="{first_name}, a new chapter", body="Your family cover deserves a quick look.")

    monkeypatch.setattr(llm, "generate_copy", fake)
    monkeypatch.setattr(fb, "choose_variant", lambda *a, **k: ("warm", {}))
    feed = compute_feed(conn, "c_001", NOW)
    hl = next(b for b in feed["screen"]["blocks"] if b["type"] == "highlight")
    assert hl["title"] == "Emma, a new chapter" and feed["journal"]["render"]["source"] == "llm"
    conn.execute("DELETE FROM action_events")
    conn.execute("DELETE FROM decisions")
    feed2 = compute_feed(conn, "c_001", NOW)                     # same segment x action x language x tone
    assert len(calls) == 1 and feed2["journal"]["render"]["source"] == "cache:llm"


def test_llm_failure_falls_back_to_template(conn, monkeypatch):
    monkeypatch.setattr(llm, "generate_copy", lambda prompt: None)
    feed = compute_feed(conn, "c_005", NOW)
    assert feed["journal"]["render"]["source"] == "template"
    assert any(b["type"] == "highlight" for b in feed["screen"]["blocks"])


def test_why_panel_is_built_from_engine_not_llm(conn, monkeypatch):
    monkeypatch.setattr(llm, "generate_copy",
                        lambda p: LlmCopy(title="Hello", body="We analysed all your health data in detail."))
    feed = compute_feed(conn, "c_001", NOW)
    why = next(b for b in feed["screen"]["blocks"] if b["type"] == "why_panel")
    assert "Recent purchases in baby stores" in why["signals_used"]
    assert all("health" not in s for s in why["signals_used"])


class _Resp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


def test_gemini_client_parses_and_validates(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(settings, gemini_api_key="test-key"))
    good = _json.dumps({"title": "A good start", "body": "A simple rule to organise your first salary."})
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(good))
    assert llm.generate_copy("{}").title == "A good start"
    bad = _json.dumps({"title": "Offer", "body": "Click <a href='x'>this link</a> now"})
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(bad))
    assert llm.generate_copy("{}") is None
