"""Simulation de 30 jours de boucle de feedback sur une population synthétique.

But : montrer que les scores d'efficacité évoluent, que le bandit converge vers la meilleure variante
de ton, et alimenter le tableau de bord conseiller. Le feedback est SIMULÉ (voir README).

Usage : python -m scripts.simulate_feedback [--customers 400] [--days 30] [--seed 7]
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import get_conn, init_db  # noqa: E402
from app.engine import feedback as fb  # noqa: E402
from app.engine.catalog import CATALOG  # noqa: E402

# Quelles actions un segment peut recevoir (grossièrement réaliste)
SEGMENT_ACTIONS = {
    "18-25/single": ["first_salary_budget", "student_to_standard", "overdraft_alert"],
    "26-44/couple": ["family_insurance_review", "loan_simulation_resume", "overdraft_alert"],
    "26-44/family": ["family_insurance_review", "family_budget_support", "overdraft_alert", "fixed_rate_end_review"],
    "45-64/family": ["fixed_rate_end_review", "car_insurance_renewal", "pension_savings_tax", "retirement_planning"],
    "65+/couple_senior": ["grandchild_savings_info", "scam_pause"],
    "65+/single": ["scam_pause", "grandchild_savings_info"],
}
AGES = {"18-25": (19, 25), "26-44": (26, 44), "45-64": (45, 64), "65+": (65, 85)}

# Probabilités de réaction de base : (completed, clicked, not_now, never). Le reste = vu / ignoré.
BASE = {
    "family_insurance_review": (0.22, 0.20, 0.10, 0.03),
    "family_budget_support": (0.35, 0.20, 0.05, 0.01),
    "grandchild_savings_info": (0.18, 0.25, 0.06, 0.02),
    "scam_pause": (0.55, 0.15, 0.02, 0.00),
    "first_salary_budget": (0.30, 0.25, 0.08, 0.02),
    "student_to_standard": (0.25, 0.15, 0.10, 0.02),
    "overdraft_alert": (0.40, 0.20, 0.05, 0.01),
    "loan_simulation_resume": (0.15, 0.25, 0.15, 0.04),
    "fixed_rate_end_review": (0.20, 0.25, 0.10, 0.02),
    "car_insurance_renewal": (0.45, 0.15, 0.05, 0.01),
    "pension_savings_tax": (0.25, 0.20, 0.10, 0.03),
    "retirement_planning": (0.20, 0.20, 0.08, 0.02),
}
# Effet (caché) de la variante : ce que le bandit doit découvrir
WARM_BONUS = {"family_insurance_review": 0.10, "grandchild_savings_info": 0.08, "first_salary_budget": 0.06,
              "family_budget_support": 0.05, "scam_pause": -0.10, "overdraft_alert": -0.06, "car_insurance_renewal": -0.05}


def sample_reaction(rng: random.Random, action_id: str, variant: str) -> str:
    comp, click, not_now, never = BASE[action_id]
    if variant == "warm":
        comp = max(0.0, comp + WARM_BONUS.get(action_id, 0.0))
    r = rng.random()
    for reaction, p in (("completed", comp), ("clicked", click), ("not_now", not_now), ("never", never)):
        if r < p:
            return reaction
        r -= p
    return "seen" if rng.random() < 0.6 else "ignored"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=400)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    init_db()
    now = settings.demo_now
    with get_conn() as conn:
        # Nettoyage d'une simulation précédente
        conn.execute("DELETE FROM suppressions WHERE customer_ref IN (SELECT customer_ref FROM action_events WHERE simulated = 1)")
        conn.execute("DELETE FROM action_events WHERE simulated = 1")
        conn.execute("DELETE FROM decisions WHERE customer_id LIKE 'sim_%'")
        conn.execute("DELETE FROM customers WHERE id LIKE 'sim_%'")
        population = []
        segments = list(SEGMENT_ACTIONS)
        for i in range(args.customers):
            seg = rng.choice(segments)
            band, household = seg.split("/")
            age = rng.randint(*AGES[band])
            cid = f"sim_{i:05d}"
            conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (cid, f"Client simulé {i}", "Client", age, "n/a", household, "n/a", rng.choice(["fr", "nl"]),
                          "medium", 0.0, "population simulée"))
            population.append((cid, fb.segment_of(age, household), fb.customer_ref(conn, cid)))
        sent = 0
        for day in range(args.days, 0, -1):
            t = now - timedelta(days=day, hours=rng.randint(0, 8))
            for cid, seg, ref in population:
                if rng.random() > 0.12:          # ~12 % des clients reçoivent une action un jour donné
                    continue
                options = [a for a in SEGMENT_ACTIONS[seg] if not fb.is_suppressed(conn, ref, a, t)]
                if not options:
                    continue
                action_id = rng.choice(options)
                variant, _ = fb.choose_variant(conn, action_id, seg, CATALOG[action_id].variants, t, rng)
                did = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO decisions(id, customer_id, created_at, action_id, action_family, channel, score, variant, journal_json, screen_json)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (did, cid, t.isoformat(), action_id, CATALOG[action_id].family, "app", 0.0, variant, "{}", "{}"),
                )
                fb.record_sent(conn, did, ref, action_id, seg, "app", variant, t, simulated=True)
                fb.record_reaction(conn, did, sample_reaction(rng, action_id, variant), t)
                sent += 1
    print(f"Simulation terminée : {args.customers} clients synthétiques, {args.days} jours, {sent} actions envoyées.")
    print("Ouvrez l'espace conseiller (/conseiller) pour voir l'efficacité, le bandit et l'équité.")


if __name__ == "__main__":
    main()
