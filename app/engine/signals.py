"""Stage 2: derived signals (the customer's "states").

Each signal carries:
  - a confidence between 0 and 1 (the engine only acts above 0.6),
  - the data families it used (for consent and the "why am I seeing this" panel),
  - human-readable evidence codes (translated in app/i18n.py).
Everything is deterministic: same snapshot -> same signals. This is what makes the engine auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.features import Snapshot, salary_cv


@dataclass
class Signal:
    name: str                       # life_event, financial_stress, intent, scam_risk, ...
    value: str | int | float
    confidence: float
    families: tuple[str, ...]
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "confidence": round(self.confidence, 2),
                "families": list(self.families), "evidence": self.evidence}


@dataclass
class Signals:
    items: list[Signal]
    financial_stress: int
    income_stability: str
    channel_pref: str
    app_active: bool

    def by_value(self, name: str, value) -> Signal | None:
        return next((s for s in self.items if s.name == name and s.value == value), None)

    def first(self, name: str) -> Signal | None:
        return next((s for s in self.items if s.name == name), None)

    def to_dict(self) -> dict:
        return {"signals": [s.to_dict() for s in self.items], "financial_stress": self.financial_stress,
                "income_stability": self.income_stability, "channel_pref": self.channel_pref, "app_active": self.app_active}


def _cap(x: float) -> float:
    return max(0.0, min(0.95, x))


def derive(s: Snapshot, month: int) -> Signals:
    items: list[Signal] = []
    tx, dig, prod, prof = s.allowed("transactions"), s.allowed("digital"), s.allowed("products"), s.allowed("profile")

    # --- Life event: baby -----------------------------------------------------------
    conf, ev, fams = 0.0, [], set()
    if tx and s.baby_tx_60d >= 1:
        conf += 0.45 + (0.10 if s.baby_tx_60d >= 3 else 0.0)
        ev.append("baby_purchases"); fams.add("transactions")
    if conf and dig and s.simulations.get("sim_family_insurance") in ("start", "abandon"):
        conf += 0.35; ev.append("sim_family_insurance"); fams.add("digital")
    if conf and prof and s.age and 22 <= s.age <= 45 and s.household in ("couple", "family"):
        conf += 0.10; ev.append("household_young"); fams.add("profile")
    if conf:
        items.append(Signal("life_event", "baby", _cap(conf), tuple(sorted(fams)), ev))

    # --- Life event: grandchild (grandparents' side) ----------------------------------
    conf, ev, fams = 0.0, [], set()
    if tx and s.birth_gift_90d:
        conf += 0.5; ev.append("birth_gift"); fams.add("transactions")
    if tx and s.recurring_family_transfer and conf:
        conf += 0.25; ev.append("recurring_family_transfer")
    if conf and prof and s.age and s.age >= 55:
        conf += 0.15; ev.append("age_55_plus"); fams.add("profile")
    if conf:
        items.append(Signal("life_event", "grandchild", _cap(conf), tuple(sorted(fams)), ev))

    # --- Life event: first job --------------------------------------------------------
    if tx and s.monthly_salary and s.monthly_salary[-1] > 0 and sum(1 for v in s.monthly_salary[:-1] if v > 0) == 0:
        conf, ev, fams = 0.65, ["first_salary"], {"transactions"}
        if prod and "student_account" in s.products:
            conf += 0.15; ev.append("student_account"); fams.add("products")
        if prof and s.age and s.age <= 27:
            conf += 0.10; fams.add("profile")
        items.append(Signal("life_event", "first_job", _cap(conf), tuple(sorted(fams)), ev))

    # --- Life event: likely income loss -----------------------------------------------
    if tx and sum(1 for v in s.monthly_salary[:-1] if v > 0) >= 4 and (s.days_since_last_salary or 0) > 38:
        items.append(Signal("life_event", "income_loss", 0.7, ("transactions",), ["salary_missing"]))

    # --- Life event: housing ----------------------------------------------------------
    conf, ev, fams = 0.0, [], set()
    if tx and s.housing_costs_60d:
        conf += 0.5; ev.append("housing_costs"); fams.add("transactions")
    if dig and s.simulations.get("sim_loan") == "abandon":
        conf += 0.35; ev.append("sim_loan_abandoned"); fams.add("digital")
    if dig and s.page_views_30d.get("loan_info", 0) >= 3:
        conf += 0.2; ev.append("loan_pages"); fams.add("digital")
    if conf:
        items.append(Signal("life_event", "housing", _cap(conf), tuple(sorted(fams)), ev))

    # --- Retirement --------------------------------------------------------------------
    if prof and prod and s.age and 60 <= s.age <= 66 and s.loan_end_days is not None and s.loan_end_days <= 365:
        items.append(Signal("life_event", "retirement", 0.7, ("products", "profile"), ["retirement_age"]))

    # --- Financial stress (level 0-3) ------------------------------------------------
    stress, ev = 0, []
    if tx:
        b = s.month_end_balances
        if len(b) >= 4 and b[0] > b[1] > b[2] > b[3]:
            stress += 1; ev.append("balance_down_3m")
        sv = s.monthly_savings
        if len(sv) == 3 and sv[0] > sv[2]:
            stress += 1; ev.append("savings_down")
        if s.late_fees_90d >= 2:
            stress += 1; ev.append("late_fees")
        overdraft = s.balance_now is not None and s.balance_now - s.upcoming_debits_7d < 0
        if overdraft:
            items.append(Signal("overdraft_risk", "7d", 0.8, ("transactions",), ["overdraft_forecast"]))
            if stress:
                stress += 1; ev.append("overdraft_forecast")
        stress = min(stress, 3)
        if stress:
            items.append(Signal("financial_stress", stress, 0.6 + 0.1 * stress, ("transactions",), ev))

    # --- Intent ------------------------------------------------------------------------
    if dig and s.simulations.get("sim_loan") == "abandon":
        conf = 0.5 + (0.3 if s.page_views_30d.get("loan_info", 0) >= 3 else 0.0)
        items.append(Signal("intent", "mortgage", conf, ("digital",), ["sim_loan_abandoned"] + (["loan_pages"] if conf > 0.5 else [])))

    # --- Scam risk (legal basis: fraud prevention) -----------------------------------
    pt = s.pending_transfer
    if pt and pt["beneficiary_is_new"]:
        conf, ev = 0.35, ["new_beneficiary"]
        if pt["amount"] >= 2000:
            conf += 0.3; ev.append("unusual_amount")
        if s.security_age >= 65:
            conf += 0.2; ev.append("senior_security")
        kind = "crypto" if pt["beneficiary_type"] == "crypto_platform" else "transfer"
        if kind == "crypto":
            conf += 0.25; ev.append("crypto_platform")
        items.append(Signal("scam_risk", kind, _cap(conf), ("security",), ev))

    # --- Product deadlines ---------------------------------------------------------------
    if prod and s.fixed_rate_end_days is not None and 0 < s.fixed_rate_end_days <= 120:
        items.append(Signal("deadline", "fixed_rate_end", 0.9, ("products",), ["fixed_rate_end"]))
    if prod and s.car_renewal_days is not None and 0 < s.car_renewal_days <= 30:
        items.append(Signal("deadline", "car_renewal", 0.9, ("products",), ["car_renewal"]))
    if prod and s.pension_room and "pension_savings" in s.products and month in (10, 11, 12):
        items.append(Signal("calendar", "pension_tax", 0.65, ("products",), ["pension_room"]))

    # --- Income stability and channel preference ----------------------------------------
    cv = salary_cv(s.monthly_salary) if tx else None
    income_stability = "unknown" if cv is None else ("stable" if cv < 0.1 else "variable")
    # Channel preference: low-digital customers who don't open the app are reached by voice,
    # active or very digital customers in the app, everybody else by push notification.
    app_active = dig and s.app_events_7d >= 2
    if s.digital_level == "low" and not app_active:
        channel_pref = "voice"
    elif app_active or s.digital_level == "high":
        channel_pref = "app"
    else:
        channel_pref = "push"

    return Signals(items=items, financial_stress=stress, income_stability=income_stability,
                   channel_pref=channel_pref, app_active=bool(app_active))
