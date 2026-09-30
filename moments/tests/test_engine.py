"""Tests du moteur : décisions par persona, garde-fous, consentement, art. 9, feedback, rendu LLM validé."""
import random
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config import settings
from app.engine import feedback as fb
from app.engine.decision import Context, decide
from app.engine.features import build_snapshot
from app.engine.service import compute_feed, set_consent
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
}


def _decide(conn, cid, now=NOW, **ctx):
    snap = build_snapshot(conn, cid, now)
    sig = derive(snap, now.month)
    return snap, sig, decide(snap, sig, Context(now=now, **ctx))


@pytest.mark.parametrize("cid,expected", EXPECTED.items())
def test_persona_decisions(conn, cid, expected):
    _, _, d = _decide(conn, cid)
    assert (d.action_id, d.channel) == expected


def test_same_signal_opposite_decision(conn):
    """Le moment fort de la démo : même signal bébé, décision opposée selon la situation."""
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
    snap, sig, d = _decide(conn, "c_001")
    assert snap.simulations == {} and "digital" not in sig.first("life_event").families
    set_consent(conn, "c_001", "transactions", False, NOW)
    _, sig, d = _decide(conn, "c_001")
    assert sig.first("life_event") is None and d.action_id == "abstain"


def test_fraud_prevention_ignores_marketing_consent(conn):
    for fam in ("transactions", "digital", "products", "profile"):
        set_consent(conn, "c_004", fam, False, NOW)
    _, _, d = _decide(conn, "c_004")
    assert d.action_id == "scam_pause"


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
    _, _, d = _decide(conn, "c_003", now=night)            # information : voix -> reportée dans l'app
    assert d.channel == "app" and "quiet_hours" in d.guardrails
    _, _, d = _decide(conn, "c_004", now=night)            # protection : autorisée la nuit
    assert d.channel == "voice" and "quiet_hours_overridden_for_protection" in d.guardrails


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


# ---------------------------------------------------------------- Rendu LLM
@pytest.mark.parametrize("bad", [
    {"title": "Offre", "body": "<script>alert(1)</script> cliquez vite"},
    {"title": "Offre", "body": "Rendez-vous sur https://evil.example pour valider"},
    {"title": "Offre", "body": "Profitez d'un taux exceptionnel de 1,9 % dès aujourd'hui"},
    {"title": "Offre", "body": "Bonjour {customer_id}, voici votre offre personnalisée"},
])
def test_llm_output_validation_rejects(bad):
    with pytest.raises(ValidationError):
        LlmCopy.model_validate(bad)


def test_llm_output_validation_accepts_placeholder():
    c = LlmCopy.model_validate({"title": "Bonjour {first_name}", "body": "Un petit mot pour vous aider à bien démarrer."})
    assert "{first_name}" in c.title


def test_llm_path_cached_and_personalized(conn, monkeypatch):
    calls = []

    def fake(prompt):
        calls.append(prompt)
        assert "c_001" not in prompt and "Emma" not in prompt       # aucune donnée identifiante envoyée au LLM
        return LlmCopy(title="{first_name}, un nouveau chapitre", body="Votre couverture familiale mérite un coup d'œil.")

    monkeypatch.setattr(llm, "generate_copy", fake)
    monkeypatch.setattr(fb, "choose_variant", lambda *a, **k: ("warm", {}))
    feed = compute_feed(conn, "c_001", NOW)
    hl = next(b for b in feed["screen"]["blocks"] if b["type"] == "highlight")
    assert hl["title"] == "Emma, un nouveau chapitre" and feed["journal"]["render"]["source"] == "llm"
    conn.execute("DELETE FROM action_events")
    conn.execute("DELETE FROM decisions")
    feed2 = compute_feed(conn, "c_001", NOW)                     # même segment × action × langue × ton
    assert len(calls) == 1 and feed2["journal"]["render"]["source"] == "cache:llm"


def test_llm_failure_falls_back_to_template(conn, monkeypatch):
    monkeypatch.setattr(llm, "generate_copy", lambda prompt: None)
    feed = compute_feed(conn, "c_005", NOW)
    assert feed["journal"]["render"]["source"] == "template"
    assert any(b["type"] == "highlight" for b in feed["screen"]["blocks"])


def test_why_panel_is_built_from_engine_not_llm(conn, monkeypatch):
    monkeypatch.setattr(llm, "generate_copy",
                        lambda p: LlmCopy(title="Bonjour", body="Nous avons analysé toutes vos données de santé."))
    feed = compute_feed(conn, "c_001", NOW)
    why = next(b for b in feed["screen"]["blocks"] if b["type"] == "why_panel")
    assert "Achats récents dans des magasins pour bébé" in why["signals_used"]
    assert all("santé" not in s for s in why["signals_used"])


class _Resp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


def test_gemini_client_parses_and_validates(monkeypatch):
    import json as _json
    from dataclasses import replace

    monkeypatch.setattr(llm, "settings", replace(settings, gemini_api_key="test-key"))
    good = _json.dumps({"title": "Bien démarrer", "body": "Une règle simple pour organiser votre premier salaire."})
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(good))
    assert llm.generate_copy("{}").title == "Bien démarrer"
    bad = _json.dumps({"title": "Offre", "body": "Cliquez sur <a href='x'>ce lien</a> maintenant"})
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _Resp(bad))
    assert llm.generate_copy("{}") is None
