"""Stage 1 -> 2: from raw data to an aggregated "snapshot" per customer.

In production, this runs as a batch job in the data warehouse (SQL / Spark) on 100% of customers.
Here it runs in Python on synthetic data. The decision engine NEVER sees raw transactions,
only this snapshot.

Privacy by design: a signal family switched off by the customer is simply not computed.
"""
from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.engine.sensitive import split_sensitive

# Signal families the customer can switch on / off
CONSENT_FAMILIES = ("transactions", "digital", "products", "profile")

PENSION_DEDUCTIBLE_CAP = 1020.0   # indicative cap, to be configured per tax year
RECURRING_CATEGORIES = {"rent", "mortgage_payment", "utilities", "loan_payment", "insurance_premium", "telecom"}


@dataclass
class Snapshot:
    customer_id: str
    first_name: str
    language: str
    digital_level: str
    consents: dict[str, bool]
    # Legal basis "fraud prevention": always available, cannot be switched off
    security_age: int
    pending_transfer: dict | None = None
    known_beneficiaries: int = 0
    # "profile" family
    age: int | None = None
    household: str | None = None
    status: str | None = None
    # "transactions" family
    excluded_sensitive: int = 0
    balance_now: float | None = None
    month_end_balances: list[float] = field(default_factory=list)     # oldest to newest
    monthly_salary: list[float] = field(default_factory=list)          # 6 months, oldest to newest
    days_since_last_salary: int | None = None
    monthly_savings: list[float] = field(default_factory=list)         # 3 months
    late_fees_90d: int = 0
    baby_spend_60d: float = 0.0
    baby_tx_60d: int = 0
    birth_gift_90d: int = 0
    recurring_family_transfer: bool = False
    housing_costs_60d: int = 0
    upcoming_debits_7d: float = 0.0
    # "digital" family
    app_events_7d: int = 0
    simulations: dict[str, str] = field(default_factory=dict)         # screen -> last status
    page_views_30d: dict[str, int] = field(default_factory=dict)
    # "products" family
    products: list[str] = field(default_factory=list)
    fixed_rate_end_days: int | None = None
    car_renewal_days: int | None = None
    loan_end_days: int | None = None
    pension_room: bool = False                                          # remaining deductible pension allowance

    def allowed(self, family: str) -> bool:
        return self.consents.get(family, True)


def _parse(d: str) -> date:
    return datetime.fromisoformat(d).date()


def _month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


def _last_n_months(today: date, n: int) -> list[tuple[int, int]]:
    keys = []
    y, m = today.year, today.month
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        keys.append((y, m))
    return list(reversed(keys))  # complete months, oldest to newest


def load_consents(conn: sqlite3.Connection, customer_id: str) -> dict[str, bool]:
    rows = conn.execute("SELECT family, enabled FROM consents WHERE customer_id = ?", (customer_id,)).fetchall()
    consents = {f: True for f in CONSENT_FAMILIES}
    consents.update({r["family"]: bool(r["enabled"]) for r in rows})
    return consents


def build_snapshot(conn: sqlite3.Connection, customer_id: str, now: datetime) -> Snapshot:
    c = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if c is None:
        raise KeyError(customer_id)
    today = now.date()
    consents = load_consents(conn, customer_id)
    snap = Snapshot(
        customer_id=c["id"], first_name=c["first_name"], language=c["language"],
        digital_level=c["digital_level"], consents=consents, security_age=c["age"],
    )

    # --- Security (fraud prevention, always on) ---
    pt = conn.execute(
        "SELECT * FROM pending_transfers WHERE customer_id = ? AND status IN ('pending','held') ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    if pt:
        snap.pending_transfer = dict(pt)
    snap.known_beneficiaries = conn.execute(
        "SELECT COUNT(DISTINCT counterparty) FROM transactions WHERE customer_id = ? AND amount < 0 AND counterparty != ''",
        (customer_id,),
    ).fetchone()[0]

    # --- Profile ---
    if snap.allowed("profile"):
        snap.age, snap.household, snap.status = c["age"], c["household"], c["status"]

    # --- Transactions ---
    if snap.allowed("transactions"):
        rows = [dict(r) for r in conn.execute(
            "SELECT date, amount, category, label, counterparty FROM transactions WHERE customer_id = ? AND date <= ? ORDER BY date",
            (customer_id, today.isoformat()),
        )]
        txs, excluded = split_sensitive(rows)
        snap.excluded_sensitive = excluded
        # The balance stays exact (it includes every transaction), but no sensitive category is ever read.
        balance = c["opening_balance"]
        month_end: dict[tuple[int, int], float] = {}
        for t in rows:
            balance += t["amount"]
            month_end[_month_key(_parse(t["date"]))] = balance
        snap.balance_now = round(balance, 2)

        months6 = _last_n_months(today, 6)
        months3 = months6[-3:]
        before = [k for k in month_end if k < months6[0]]
        running = month_end[max(before)] if before else c["opening_balance"]
        for k in months6:
            running = month_end.get(k, running)
            if k in months6[-4:]:
                snap.month_end_balances.append(round(running, 2))  # 4 month-ends -> 3 variations

        salary = {k: 0.0 for k in months6}
        savings = {k: 0.0 for k in months3}
        last_salary: date | None = None
        last_month_recurring: list[dict] = []
        prev_month = months6[-1]
        for t in txs:
            d = _parse(t["date"])
            k = _month_key(d)
            age_days = (today - d).days
            cat = t["category"]
            if cat == "salary":
                if k in salary:
                    salary[k] += t["amount"]
                last_salary = d if (last_salary is None or d > last_salary) else last_salary
            elif cat == "savings_transfer" and k in savings:
                savings[k] += -t["amount"]
            elif cat == "late_fee" and age_days <= 90:
                snap.late_fees_90d += 1
            elif cat == "baby" and age_days <= 60:
                snap.baby_spend_60d += -t["amount"]
                snap.baby_tx_60d += 1
            elif cat == "birth_gift" and age_days <= 90:
                snap.birth_gift_90d += 1
            elif cat in ("notary", "moving_company") and age_days <= 60:
                snap.housing_costs_60d += 1
            if cat in RECURRING_CATEGORIES and k == prev_month:
                last_month_recurring.append(t)
        snap.monthly_salary = [round(salary[k], 2) for k in months6]
        snap.monthly_savings = [round(savings[k], 2) for k in months3]
        snap.days_since_last_salary = (today - last_salary).days if last_salary else None

        # Recurring family transfer: same beneficiary, 3 consecutive months
        fam: dict[str, set] = {}
        for t in txs:
            if t["category"] == "family_transfer":
                fam.setdefault(t["counterparty"], set()).add(_month_key(_parse(t["date"])))
        snap.recurring_family_transfer = any(len(ms & set(months3)) >= 3 for ms in fam.values())

        # Forecast: last month's recurring debits that will fall again within the next 7 days
        for t in last_month_recurring:
            d = _parse(t["date"])
            try:
                next_d = d.replace(year=today.year, month=today.month)
            except ValueError:
                continue
            if next_d < today:
                continue
            already_paid = any(
                _parse(x["date"]) >= today.replace(day=1) and x["category"] == t["category"] for x in txs
            )
            if (next_d - today).days <= 7 and not already_paid:
                snap.upcoming_debits_7d += -t["amount"]
        snap.upcoming_debits_7d = round(snap.upcoming_debits_7d, 2)

    # --- Digital ---
    if snap.allowed("digital"):
        since7 = (now - timedelta(days=7)).isoformat()
        since30 = (now - timedelta(days=30)).isoformat()
        for e in conn.execute(
            "SELECT ts, screen, action FROM app_events WHERE customer_id = ? AND ts <= ? ORDER BY ts",
            (customer_id, now.isoformat()),
        ):
            if e["ts"] >= since7:
                snap.app_events_7d += 1
            if e["screen"].startswith("sim_"):
                snap.simulations[e["screen"]] = e["action"]
            if e["action"] == "view" and e["ts"] >= since30:
                snap.page_views_30d[e["screen"]] = snap.page_views_30d.get(e["screen"], 0) + 1

    # --- Products ---
    if snap.allowed("products"):
        for p in conn.execute("SELECT product_type, end_date FROM products WHERE customer_id = ?", (customer_id,)):
            snap.products.append(p["product_type"])
            if p["end_date"]:
                days = (_parse(p["end_date"]) - today).days
                if p["product_type"] == "mortgage_fixed_rate":
                    snap.fixed_rate_end_days = days
                elif p["product_type"] == "car_insurance":
                    snap.car_renewal_days = days
                elif p["product_type"] in ("mortgage", "consumer_loan"):
                    snap.loan_end_days = days
        if "pension_savings" in snap.products and snap.allowed("transactions"):
            paid = conn.execute(
                "SELECT COALESCE(SUM(-amount), 0) FROM transactions WHERE customer_id = ? AND category = 'pension_contribution' AND date >= ?",
                (customer_id, f"{today.year}-01-01"),
            ).fetchone()[0]
            snap.pension_room = paid < PENSION_DEDUCTIBLE_CAP
    return snap


def salary_cv(values: list[float]) -> float | None:
    """Coefficient of variation of the salary (None if fewer than 3 paid months)."""
    paid = [v for v in values if v > 0]
    if len(paid) < 3:
        return None
    mean = statistics.mean(paid)
    return statistics.pstdev(paid) / mean if mean else None
