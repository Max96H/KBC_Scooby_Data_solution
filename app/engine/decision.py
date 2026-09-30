"""Stage 3: the decision engine.

Derived signals -> candidate actions -> score -> guardrails -> ONE action (or abstention) + channel.

The LLM never takes part here: the decision is deterministic and auditable, and every step is
recorded in a "journal" used both by the "why am I seeing this" panel and by audits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from app.engine.catalog import CATALOG, Action
from app.engine.features import Snapshot
from app.engine.feedback import EFFICIENCY_PRIOR, apply_learning
from app.engine.signals import Signal, Signals

# --- Score weights. Ethical choice: customer value weighs more than bank value.
WEIGHTS = {"value_customer": 0.35, "urgency": 0.25, "confidence": 0.20, "value_bank": 0.10, "sensitivity": -0.10}
CONFIDENCE_THRESHOLD = 0.6
STRESS_NO_SALES = 2
QUIET_START, QUIET_END = 21, 8          # no notification or call between 9 pm and 8 am
PROACTIVE_CHANNELS = {"push", "voice"}
CHANNELS = ("app", "push", "voice", "human")

# Trigger rules: (signal name, value) -> candidate actions
TRIGGERS: dict[tuple[str, object], list[str]] = {
    ("life_event", "baby"): ["family_insurance_review", "family_budget_support"],
    ("life_event", "grandchild"): ["grandchild_savings_info"],
    ("life_event", "first_job"): ["first_salary_budget", "student_to_standard"],
    ("life_event", "income_loss"): ["job_loss_support"],
    ("life_event", "housing"): ["loan_simulation_resume"],
    ("intent", "mortgage"): ["loan_simulation_resume"],
    ("life_event", "retirement"): ["retirement_planning"],
    ("overdraft_risk", "7d"): ["overdraft_alert"],
    ("scam_risk", "transfer"): ["scam_pause"],
    ("scam_risk", "crypto"): ["crypto_verification"],
    ("deadline", "fixed_rate_end"): ["fixed_rate_end_review"],
    ("deadline", "car_renewal"): ["car_insurance_renewal"],
    ("calendar", "pension_tax"): ["pension_savings_tax"],
}


def _extra_condition(action_id: str, snap: Snapshot, sig: Signals) -> bool:
    """Extra conditions specific to some actions."""
    if action_id == "family_budget_support":
        return sig.financial_stress >= 1            # budget support only makes sense under financial pressure
    if action_id == "student_to_standard":
        return "student_account" in snap.products
    if action_id == "loan_simulation_resume":
        return snap.simulations.get("sim_loan") == "abandon"
    return True


@dataclass
class Context:
    """What the engine needs besides the snapshot. Injected to stay testable and fast."""
    now: datetime
    efficiency: Callable[[str], tuple[float, int]] = lambda _a: (EFFICIENCY_PRIOR, 0)
    suppressed: Callable[[str], str | None] = lambda _a: None
    recent_proactive: bool = False          # a proactive nudge was already sent in the last 7 days


@dataclass
class Candidate:
    action: Action
    signal: Signal
    score_base: float = 0.0
    efficiency: float = EFFICIENCY_PRIOR
    feedback_n: int = 0
    score: float = 0.0
    status: str = "eligible"                # eligible | blocked | chosen
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action.id, "family": self.action.family, "product": self.action.product,
            "trigger": f"{self.signal.name}={self.signal.value} (conf {self.signal.confidence:.2f})",
            "confidence": round(self.signal.confidence, 2),
            "score_base": round(self.score_base, 3), "efficiency": round(self.efficiency, 3),
            "feedback_n": self.feedback_n, "score": round(self.score, 3),
            "is_commercial": self.action.is_commercial, "status": self.status, "reasons": self.reasons,
        }


@dataclass
class Decision:
    action: Action | None
    signal: Signal | None
    channel: str
    score: float
    abstain_reason: str | None
    requires_human: bool
    candidates: list[Candidate]
    guardrails: list[str]
    channel_reason: str                     # code, translated by the front end

    @property
    def action_id(self) -> str:
        return self.action.id if self.action else "abstain"

    @property
    def family(self) -> str:
        return self.action.family if self.action else "abstain"


def base_score(action: Action, confidence: float) -> float:
    return (WEIGHTS["value_customer"] * action.value_customer + WEIGHTS["urgency"] * action.urgency
            + WEIGHTS["confidence"] * confidence + WEIGHTS["value_bank"] * action.value_bank
            + WEIGHTS["sensitivity"] * action.sensitivity)


def _quiet(now: datetime) -> bool:
    return now.hour >= QUIET_START or now.hour < QUIET_END


def choose_channel(action: Action, snap: Snapshot, sig: Signals, ctx: Context) -> tuple[str, str, list[str]]:
    """Return (channel, reason code, guardrails triggered).

    Order of the rules (the first match wins):
      1. sensitive topic                     -> human (appointment offer + advisor task)
      2. low-digital customer, app unused    -> voice
      3. customer active in the app          -> app (card on the home screen)
      4. urgent and customer inactive        -> push notification
      5. otherwise                           -> app (shown at the next opening)
    Then the frequency cap and quiet hours can downgrade push / voice to the app.
    """
    notes: list[str] = []
    if action.sensitive_topic:
        return "human", "sensitive_topic", notes
    if sig.channel_pref == "voice":
        channel, reason = "voice", "low_digital"
    elif sig.app_active:
        channel, reason = "app", "app_active"
    elif action.urgency >= 0.7:
        channel, reason = "push", "urgent_inactive"
    else:
        channel, reason = "app", "next_app_open"
    if channel in PROACTIVE_CHANNELS and action.family != "protect":
        if ctx.recent_proactive:
            notes.append("frequency_cap")
            channel, reason = "app", "frequency_cap"
        elif _quiet(ctx.now):
            notes.append("quiet_hours")
            channel, reason = "app", "quiet_hours"
    if channel in PROACTIVE_CHANNELS and action.family == "protect" and _quiet(ctx.now):
        notes.append("quiet_hours_overridden_for_protection")
    return channel, reason, notes


def decide(snap: Snapshot, sig: Signals, ctx: Context) -> Decision:
    guardrails: list[str] = []

    # 1. Generate candidates (if several signals lead to the same action, keep the most confident one)
    best_signal: dict[str, Signal] = {}
    for s in sig.items:
        for action_id in TRIGGERS.get((s.name, s.value), []):
            if not _extra_condition(action_id, snap, sig):
                continue
            if action_id not in best_signal or s.confidence > best_signal[action_id].confidence:
                best_signal[action_id] = s
    candidates = [Candidate(action=CATALOG[a], signal=s) for a, s in best_signal.items()]

    # 2. Score and apply guardrails
    for c in candidates:
        a = c.action
        c.score_base = base_score(a, c.signal.confidence)
        c.efficiency, c.feedback_n = ctx.efficiency(a.id)
        c.score = apply_learning(c.score_base, c.efficiency)
        # Consent (the "fraud prevention" legal basis is not subject to marketing consent)
        if a.legal_basis == "consent" and any(f != "security" and not snap.allowed(f) for f in c.signal.families):
            c.status = "blocked"; c.reasons.append("consent_withdrawn")
        if c.signal.confidence < CONFIDENCE_THRESHOLD:
            c.status = "blocked"; c.reasons.append("low_confidence")
        if a.is_commercial and sig.financial_stress >= STRESS_NO_SALES:
            c.status = "blocked"; c.reasons.append("financial_stress_no_sales")
        if ctx.suppressed(a.id):
            c.status = "blocked"; c.reasons.append("suppressed_after_refusal")
        if a.involves_credit:
            c.reasons.append("credit_human_in_the_loop")

    for c in candidates:
        for r in c.reasons:
            if c.status == "blocked" and r not in guardrails:
                guardrails.append(r)

    eligible = [c for c in candidates if c.status == "eligible"]

    # 3. Arbitration: one action only. With stress >= 2, help comes first (except fraud protection).
    pool = eligible
    if sig.financial_stress >= STRESS_NO_SALES:
        protect = [c for c in eligible if c.action.family == "protect" and c.action.legal_basis == "fraud_prevention"]
        help_ = [c for c in eligible if c.action.family == "accompany"]
        if protect:
            pool = protect
        elif help_:
            pool = help_
            guardrails.append("stress_prioritizes_help")
    if not pool:
        if not candidates:
            reason = "no_signal"
        elif "financial_stress_no_sales" in guardrails:
            reason = "stress_no_sales"
        elif all("low_confidence" in c.reasons for c in candidates):
            reason = "low_confidence"
        else:
            reason = "all_blocked"
        guardrails.append("abstain")
        return Decision(None, None, "app", 0.0, reason, False, candidates, guardrails, "abstain")

    best = max(pool, key=lambda c: c.score)
    best.status = "chosen"
    for c in eligible:
        if c is not best:
            c.reasons.append("one_action_at_a_time")
    if len(eligible) > 1:
        guardrails.append("one_action_at_a_time")
    channel, channel_reason, notes = choose_channel(best.action, snap, sig, ctx)
    guardrails.extend(notes)
    return Decision(best.action, best.signal, channel, best.score, None, best.action.involves_credit,
                    candidates, guardrails, channel_reason)
