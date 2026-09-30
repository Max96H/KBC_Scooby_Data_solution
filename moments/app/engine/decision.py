"""Étage 3 : le moteur de décision.

Signaux dérivés -> actions candidates -> score -> garde-fous -> UNE action (ou l'abstention) + canal.

Le LLM n'intervient jamais ici : la décision est déterministe, auditable, et chaque étape est
consignée dans un « journal » qui sert à la fois au panneau « pourquoi je vois ça » et à l'audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from app.engine.catalog import CATALOG, Action
from app.engine.features import Snapshot
from app.engine.feedback import EFFICIENCY_PRIOR, apply_learning
from app.engine.signals import Signal, Signals

# --- Poids du score (section 5.2). Choix éthique : la valeur client pèse plus que la valeur banque.
WEIGHTS = {"value_customer": 0.35, "urgency": 0.25, "confidence": 0.20, "value_bank": 0.10, "sensitivity": -0.10}
CONFIDENCE_THRESHOLD = 0.6
STRESS_NO_SALES = 2
QUIET_START, QUIET_END = 21, 8          # pas de notification ni d'appel entre 21h et 8h
PROACTIVE_CHANNELS = {"push", "voice"}

# Règles de déclenchement : (nom du signal, valeur) -> actions candidates
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

# Conditions supplémentaires propres à certaines actions
def _extra_condition(action_id: str, snap: Snapshot, sig: Signals) -> bool:
    if action_id == "family_budget_support":
        return sig.financial_stress >= 1            # l'accompagnement budgétaire n'a de sens qu'en cas de tension
    if action_id == "student_to_standard":
        return "student_account" in snap.products
    if action_id == "loan_simulation_resume":
        return snap.simulations.get("sim_loan") == "abandon"
    return True


@dataclass
class Context:
    """Ce dont le moteur a besoin en dehors du snapshot. Injecté pour rester testable et rapide."""
    now: datetime
    efficiency: Callable[[str], tuple[float, int]] = lambda _a: (EFFICIENCY_PRIOR, 0)
    suppressed: Callable[[str], str | None] = lambda _a: None
    recent_proactive: bool = False          # un nudge proactif a déjà été envoyé dans les 7 derniers jours


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
    channel_reason: str

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
    """Retourne (canal, raison, garde-fous déclenchés)."""
    notes: list[str] = []
    if action.sensitive_topic:
        return "human", "Sujet sensible : proposition de rendez-vous avec un humain", notes
    if sig.channel_pref == "voice":
        channel, reason = "voice", "Client peu digital : message vocal"
    elif sig.app_active:
        channel, reason = "app", "Client actif dans l'app : bloc sur l'écran d'accueil"
    elif action.urgency >= 0.7:
        channel, reason = "push", "Urgence élevée et client inactif : notification"
    else:
        channel, reason = "app", "Affiché à la prochaine ouverture de l'app"
    if channel in PROACTIVE_CHANNELS and action.family != "protect":
        if ctx.recent_proactive:
            notes.append("frequency_cap")
            channel, reason = "app", "Un message proactif a déjà été envoyé cette semaine : affichage discret dans l'app"
        elif _quiet(ctx.now):
            notes.append("quiet_hours")
            channel, reason = "app", "Heures calmes : pas de notification, affichage dans l'app"
    if channel in PROACTIVE_CHANNELS and action.family == "protect" and _quiet(ctx.now):
        notes.append("quiet_hours_overridden_for_protection")
    return channel, reason, notes


def decide(snap: Snapshot, sig: Signals, ctx: Context) -> Decision:
    guardrails: list[str] = []

    # 1. Générer les candidates (si plusieurs signaux mènent à la même action, on garde le plus sûr)
    best_signal: dict[str, Signal] = {}
    for s in sig.items:
        for action_id in TRIGGERS.get((s.name, s.value), []):
            if not _extra_condition(action_id, snap, sig):
                continue
            if action_id not in best_signal or s.confidence > best_signal[action_id].confidence:
                best_signal[action_id] = s
    candidates = [Candidate(action=CATALOG[a], signal=s) for a, s in best_signal.items()]

    # 2. Scorer et appliquer les garde-fous
    for c in candidates:
        a = c.action
        c.score_base = base_score(a, c.signal.confidence)
        c.efficiency, c.feedback_n = ctx.efficiency(a.id)
        c.score = apply_learning(c.score_base, c.efficiency)
        # Consentement (la base légale "prévention fraude" n'est pas soumise au consentement marketing)
        if a.legal_basis == "consent" and any(f != "security" and not snap.allowed(f) for f in c.signal.families):
            c.status = "blocked"; c.reasons.append("consent_withdrawn")
        if c.signal.confidence < CONFIDENCE_THRESHOLD:
            c.status = "blocked"; c.reasons.append("low_confidence")
        if a.is_commercial and sig.financial_stress >= STRESS_NO_SALES:
            c.status = "blocked"; c.reasons.append("financial_stress_no_sales")
        why = ctx.suppressed(a.id)
        if why:
            c.status = "blocked"; c.reasons.append("suppressed_after_refusal")
        if a.involves_credit:
            c.reasons.append("credit_human_in_the_loop")

    for c in candidates:
        for r in c.reasons:
            if c.status == "blocked" and r not in guardrails:
                guardrails.append(r)

    eligible = [c for c in candidates if c.status == "eligible"]

    # 3. Arbitrage : une seule action. En cas de stress >= 2, l'aide passe avant tout (sauf protection).
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
        return Decision(None, None, "app", 0.0, reason, False, candidates, guardrails,
                        "S'abstenir : rien n'est affiché de manière proactive")

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


GUARDRAIL_TEXT = {
    "consent_withdrawn": "Consentement retiré pour une donnée utilisée : action écartée",
    "low_confidence": "Confiance < 0,6 : on n'agit pas",
    "financial_stress_no_sales": "Stress financier ≥ 2 : aucune vente",
    "stress_prioritizes_help": "Stress financier ≥ 2 : l'aide passe en priorité",
    "suppressed_after_refusal": "Refus récent du client : pause respectée",
    "credit_human_in_the_loop": "Crédit : décision toujours humaine (RGPD art. 22)",
    "one_action_at_a_time": "Une seule action à la fois",
    "frequency_cap": "Maximum 1 message proactif par 7 jours",
    "quiet_hours": "Heures calmes (21h–8h)",
    "quiet_hours_overridden_for_protection": "Protection anti-fraude : autorisée même en heures calmes",
    "abstain": "Le moteur s'abstient",
}

ABSTAIN_REASON_TEXT = {
    "no_signal": {"fr": "Rien dans votre situation actuelle ne justifie de vous solliciter.",
                  "nl": "Niets in uw huidige situatie rechtvaardigt dat we u contacteren."},
    "low_confidence": {"fr": "Nous ne sommes pas assez sûrs de ce dont vous avez besoin, donc nous ne supposons rien.",
                       "nl": "We zijn niet zeker genoeg van wat u nodig hebt, dus we veronderstellen niets."},
    "stress_no_sales": {"fr": "Toutes les offres commerciales sont désactivées pour vous en ce moment.",
                        "nl": "Alle commerciële aanbiedingen staan voor u momenteel uit."},
    "all_blocked": {"fr": "Vous nous avez indiqué ne pas vouloir ce type de message, et nous le respectons.",
                    "nl": "U gaf aan dit soort berichten niet te willen, en dat respecteren we."},
}
