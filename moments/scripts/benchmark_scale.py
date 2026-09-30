"""Benchmark de passage à l'échelle : combien de temps pour décider pour 2,3 M de clients ?

On génère N snapshots synthétiques (ce que produirait le batch de l'entrepôt de données), on exécute
signaux + décision + garde-fous sur un seul cœur, puis on extrapole à 2,3 M.
Le rendu LLM n'est PAS inclus : il ne concerne que les clients qui déclenchent une action, et il est caché.

Usage : python -m scripts.benchmark_scale [--n 200000] [--write docs/BENCHMARK.md]
"""
from __future__ import annotations

import argparse
import platform
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.engine.decision import Context, decide  # noqa: E402
from app.engine.features import CONSENT_FAMILIES, Snapshot  # noqa: E402
from app.engine.signals import derive  # noqa: E402

TARGET = 2_300_000


def random_snapshot(rng: random.Random, i: int) -> Snapshot:
    age = rng.randint(18, 90)
    household = rng.choice(["single", "couple", "family", "couple_senior"] if age > 60 else ["single", "couple", "family"])
    digital = rng.choices(["high", "medium", "low"], weights=[5, 3, 2 if age < 65 else 6])[0]
    consents = {f: rng.random() > 0.05 for f in CONSENT_FAMILIES}
    salary = rng.choice([0, 1800, 2400, 3200, 4500]) if age < 66 else 0
    months = [salary * rng.uniform(0.97, 1.03) if salary else 0 for _ in range(6)]
    if salary and rng.random() < 0.01:
        months = [0, 0, 0, 0, 0, salary]                     # premier salaire
    if salary and rng.random() < 0.005:
        months[-1] = 0                                       # revenu manquant
    trend = rng.choice([1, 1, 1, -1])
    base = rng.uniform(200, 20000)
    balances = [base + trend * k * rng.uniform(50, 600) for k in range(4)]
    s = Snapshot(customer_id=f"b{i}", first_name="X", language=rng.choice(["fr", "nl"]), digital_level=digital,
                 consents=consents, security_age=age)
    if consents["profile"]:
        s.age, s.household = age, household
    if consents["transactions"]:
        s.balance_now = balances[-1]
        s.month_end_balances = balances
        s.monthly_salary = months
        s.days_since_last_salary = 45 if months[-1] == 0 and salary else 6
        sv = rng.uniform(0, 500)
        s.monthly_savings = [sv, sv * rng.uniform(0.5, 1.1), sv * rng.uniform(0.3, 1.1)]
        s.late_fees_90d = rng.choices([0, 1, 2, 3], weights=[90, 6, 3, 1])[0]
        if 22 <= age <= 42 and rng.random() < 0.02:
            s.baby_tx_60d = rng.randint(1, 5)
        if age >= 55 and rng.random() < 0.01:
            s.birth_gift_90d = 1
            s.recurring_family_transfer = rng.random() < 0.5
        s.upcoming_debits_7d = rng.uniform(0, 1500)
        s.housing_costs_60d = 1 if rng.random() < 0.005 else 0
    if consents["digital"]:
        s.app_events_7d = rng.randint(0, 12) if digital != "low" else rng.randint(0, 1)
        if rng.random() < 0.02:
            s.simulations["sim_family_insurance"] = "start"
        if rng.random() < 0.01:
            s.simulations["sim_loan"] = "abandon"
            s.page_views_30d["loan_info"] = rng.randint(0, 5)
    if consents["products"]:
        s.products = ["current_account"] + [p for p, prob in (("savings", .6), ("pension_savings", .3), ("car_insurance", .4),
                                                              ("student_account", .08 if age < 26 else 0)) if rng.random() < prob]
        s.pension_room = "pension_savings" in s.products and rng.random() < 0.1
        s.fixed_rate_end_days = rng.randint(-100, 3000) if rng.random() < 0.3 else None
        s.car_renewal_days = rng.randint(-10, 365) if "car_insurance" in s.products else None
    if rng.random() < 0.001:
        s.pending_transfer = {"id": 0, "amount": rng.uniform(500, 9000), "beneficiary_is_new": 1,
                              "beneficiary_type": rng.choice(["person", "crypto_platform"]), "status": "pending", "hold_until": None}
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--write", type=str, default="")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    snaps = [random_snapshot(rng, i) for i in range(args.n)]
    ctx = Context(now=settings.demo_now)
    outcomes: Counter[str] = Counter()
    families: Counter[str] = Counter()
    channels: Counter[str] = Counter()
    guard: Counter[str] = Counter()
    start = time.perf_counter()
    for s in snaps:
        sig = derive(s, settings.demo_now.month)
        d = decide(s, sig, ctx)
        outcomes[d.action_id] += 1
        families[d.family] += 1
        if d.action:
            channels[d.channel] += 1
        for g in set(d.guardrails):
            guard[g] += 1
    elapsed = time.perf_counter() - start
    per_sec = args.n / elapsed
    full = TARGET / per_sec
    acted = args.n - outcomes["abstain"]
    lines = [
        "# Benchmark de passage à l'échelle",
        "",
        f"Généré par `python -m scripts.benchmark_scale --n {args.n}` sur {platform.processor() or platform.machine()}, Python {platform.python_version()}, **un seul cœur**.",
        "",
        "| Mesure | Valeur |",
        "| --- | --- |",
        f"| Clients synthétiques évalués | {args.n:,} |".replace(",", " "),
        f"| Temps signaux + décision + garde-fous | {elapsed:.2f} s |",
        f"| Débit | {per_sec:,.0f} clients / s |".replace(",", " "),
        f"| Extrapolation 2,3 M clients (1 cœur) | {full:.0f} s ≈ {full / 60:.1f} min |",
        f"| Extrapolation 2,3 M clients (16 cœurs) | ≈ {full / 16:.0f} s |",
        f"| Clients avec une action | {acted / args.n:.1%} |",
        f"| Abstentions | {outcomes['abstain'] / args.n:.1%} |",
        "",
        "## Répartition des décisions",
        "",
        "| Famille | Part |",
        "| --- | --- |",
        *[f"| {k} | {v / args.n:.2%} |" for k, v in families.most_common()],
        "",
        "| Canal (clients avec action) | Part |",
        "| --- | --- |",
        *[f"| {k} | {v / (acted or 1):.1%} |" for k, v in channels.most_common()],
        "",
        "## Garde-fous déclenchés",
        "",
        "| Garde-fou | Clients concernés |",
        "| --- | --- |",
        *[f"| `{k}` | {v / args.n:.2%} |" for k, v in guard.most_common()],
        "",
        "## Lecture",
        "",
        "- La décision est déterministe et coûte quelques microsecondes par client : elle peut tourner chaque nuit (ou en streaming) sur 100 % de la base.",
        "- Le LLM n'intervient que pour les clients avec une action, et le texte est réutilisé par segment × moment × langue × ton (voir le calculateur dans l'espace conseiller).",
        "- Les distributions dépendent entièrement du générateur synthétique : elles illustrent la mécanique, pas des taux réels de KBC.",
        "",
    ]
    report = "\n".join(lines)
    print(report)
    if args.write:
        Path(args.write).write_text(report, encoding="utf-8")
        print(f"Écrit dans {args.write}")


if __name__ == "__main__":
    main()
