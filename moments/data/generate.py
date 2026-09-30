"""Générateur de données 100 % synthétiques (aucune donnée réelle de KBC ni d'aucun client).

7 personas de démo, chacun construit pour illustrer une décision précise du moteur :

  emma     Jeune couple actif, bébé en route          -> PROPOSER  (assurance famille + épargne enfant, app)
  sofia    Même signal bébé + stress financier         -> ACCOMPAGNER (aucune vente, conseiller humain)
  jan      Grands-parents, peu digitaux, néerlandophones -> INFORMER (épargne petit-enfant, voix)
  marcel   Senior, virement suspect en cours            -> PROTÉGER (pause de 10 min, voix)
  yasmine  Premier salaire                              -> INFORMER (règle 50/30/20)
  thomas   Situation stable                             -> S'ABSTENIR (et le dire)
  nina     Simulation de prêt abandonnée                -> SIMPLIFIER (reprise, crédit = humain)
  conseiller  Compte conseiller (file d'attente + tableau de bord)

Usage :  python -m data.generate            (crée / réinitialise moments.db)
         DEMO_PASSWORD=... python -m data.generate   (mot de passe commun pour la démo)
"""
from __future__ import annotations

import os
import random
import secrets
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import get_conn, init_db  # noqa: E402
from app.security import hash_password  # noqa: E402

rng = random.Random(42)
NOW: datetime = settings.demo_now
TODAY: date = NOW.date()


def months_back(n: int) -> list[tuple[int, int]]:
    """Les n derniers mois complets + le mois en cours, du plus ancien au plus récent."""
    y, m = TODAY.year, TODAY.month
    out = [(y, m)]
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return list(reversed(out))


MONTHS = months_back(7)


def d(y: int, m: int, day: int) -> str:
    return date(y, m, min(day, 28)).isoformat()


class Builder:
    def __init__(self) -> None:
        self.customers: list[tuple] = []
        self.tx: list[tuple] = []
        self.events: list[tuple] = []
        self.products: list[tuple] = []
        self.pending: list[tuple] = []
        self.users: list[tuple[str, str, str | None]] = []

    def customer(self, cid, display, first, age, status, household, city, lang, digital, opening, persona, username):
        self.customers.append((cid, display, first, age, status, household, city, lang, digital, opening, persona))
        self.users.append((username, "customer", cid))

    def t(self, cid, day: str, amount, category, label, counterparty=""):
        if day <= TODAY.isoformat():
            self.tx.append((cid, day, round(amount, 2), category, label, counterparty))

    def ev(self, cid, ts: datetime, screen, action="view"):
        self.events.append((cid, ts.isoformat(), screen, action))

    def monthly(self, cid, day, amount, category, label, counterparty="", months=MONTHS):
        for (y, m) in months:
            self.t(cid, d(y, m, day), amount, category, label, counterparty)

    def groceries(self, cid, per_week, months=MONTHS):
        for (y, m) in months:
            for wk in (4, 11, 18, 25):
                self.t(cid, d(y, m, wk), -per_week * rng.uniform(0.85, 1.15), "groceries", "Supermarché", "")


def build() -> Builder:
    b = Builder()
    full = MONTHS[:-1]  # mois complets

    # ---------------- Emma : bébé, situation saine -> PROPOSER ----------------
    c = "c_001"
    b.customer(c, "Emma Janssens", "Emma", 31, "salariée", "couple", "Namur", "fr", "high", 4200.0,
               "Jeune couple actif, bébé en route", "emma")
    b.monthly(c, 25, 3100, "salary", "Salaire", "Employeur SA", full)
    b.monthly(c, 3, -1050, "rent", "Loyer", "Propriétaire")
    b.monthly(c, 10, -140, "utilities", "Énergie", "Fournisseur énergie")
    b.monthly(c, 15, -45, "telecom", "Télécom", "Opérateur")
    b.monthly(c, 26, -500, "savings_transfer", "Épargne mensuelle", "Compte épargne", full)
    b.groceries(c, 95)
    for day, amt in [("2026-08-17", -189.9), ("2026-09-02", -349.0), ("2026-09-14", -72.5), ("2026-09-28", -129.0)]:
        b.t(c, day, amt, "baby", "Petit Nid – magasin bébé", "Petit Nid")
    b.t(c, "2026-09-05", -23.4, "pharmacy", "Pharmacie", "Pharmacie du Centre")      # exclue (art. 9)
    b.t(c, "2026-09-19", -60.0, "medical", "Consultation", "Cabinet médical")         # exclue (art. 9)
    for i in range(6):
        b.ev(c, NOW - timedelta(days=i, hours=2), "home")
    b.ev(c, NOW - timedelta(days=3), "sim_family_insurance", "start")
    b.ev(c, NOW - timedelta(days=3, minutes=-5), "family_insurance_info")
    b.products += [(c, "current_account", "", None), (c, "savings", "", None),
                   (c, "family_insurance", "RC familiale", "2027-03-01"), (c, "home_insurance", "", "2027-01-15")]

    # ---------------- Sofia : même signal bébé + stress -> ACCOMPAGNER ----------------
    c = "c_002"
    b.customer(c, "Sofia Dubois", "Sofia", 34, "salariée", "family", "Charleroi", "fr", "medium", 2600.0,
               "Famille, bébé arrivé, budget sous tension", "sofia")
    b.monthly(c, 25, 2300, "salary", "Salaire", "Employeur SPRL", full)
    b.monthly(c, 3, -950, "rent", "Loyer", "Propriétaire")
    b.monthly(c, 5, -280, "loan_payment", "Prêt voiture", "Crédit auto")
    b.monthly(c, 10, -175, "utilities", "Énergie", "Fournisseur énergie")
    b.monthly(c, 15, -55, "telecom", "Télécom", "Opérateur")
    b.groceries(c, 120)
    for (y, m), amt in zip(full, [300, 300, 250, 200, 100, 0]):
        if amt:
            b.t(c, d(y, m, 26), -amt, "savings_transfer", "Épargne", "Compte épargne")
    for (y, m), extra in zip(full, [0, 0, 150, 300, 450, 520]):
        if extra:
            b.t(c, d(y, m, 19), -extra, "leisure_other", "Dépenses diverses", "")
    for day, amt in [("2026-08-08", -420.0), ("2026-08-21", -265.0), ("2026-09-06", -310.0), ("2026-09-22", -185.0)]:
        b.t(c, day, amt, "baby", "Petit Nid – magasin bébé", "Petit Nid")
    b.t(c, "2026-08-12", -15.0, "late_fee", "Frais de rappel", "Fournisseur énergie")
    b.t(c, "2026-09-14", -15.0, "late_fee", "Frais de rappel", "Opérateur")
    b.t(c, "2026-08-30", -95.0, "hospital", "Maternité – quote-part", "Hôpital")          # exclue (art. 9)
    b.ev(c, NOW - timedelta(days=5), "home")
    b.products += [(c, "current_account", "", None), (c, "savings", "", None), (c, "consumer_loan", "Prêt voiture", "2028-05-01")]

    # ---------------- Jan & Monique : petit-enfant, peu digital, NL -> INFORMER (voix) ----------------
    c = "c_003"
    b.customer(c, "Jan & Monique Peeters", "Jan", 67, "retraité", "couple_senior", "Gent", "nl", "low", 24000.0,
               "Grands-parents, peu digitaux", "jan")
    b.monthly(c, 1, 2450, "pension", "Pensioen", "Pensioendienst")
    b.monthly(c, 8, -190, "utilities", "Energie", "Energieleverancier")
    b.monthly(c, 15, -38, "telecom", "Telecom", "Operator")
    b.groceries(c, 85)
    for (y, m) in MONTHS[-4:-1]:
        b.t(c, d(y, m, 12), -150, "family_transfer", "Maandelijkse steun", "An Peeters")
    b.t(c, "2026-09-10", -500, "birth_gift", "Geboorte Lena", "An Peeters")
    b.t(c, "2026-09-03", -31.2, "pharmacy", "Apotheek", "Apotheek")                        # exclue (art. 9)
    b.products += [(c, "current_account", "", None), (c, "savings", "", None), (c, "home_insurance", "", "2027-04-01")]

    # ---------------- Marcel : virement suspect -> PROTÉGER ----------------
    c = "c_004"
    b.customer(c, "Marcel Lambert", "Marcel", 78, "retraité", "single", "Liège", "fr", "low", 15500.0,
               "Senior, virement inhabituel en cours", "marcel")
    b.monthly(c, 1, 1850, "pension", "Pension", "Service Pensions")
    b.monthly(c, 8, -130, "utilities", "Énergie", "Fournisseur énergie")
    b.groceries(c, 70)
    b.pending.append((c, (NOW - timedelta(minutes=4)).isoformat(), 4900.0, "Support Sécurité Compte", 1, "person"))
    b.products += [(c, "current_account", "", None), (c, "savings", "", None)]

    # ---------------- Yasmine : premier salaire -> INFORMER ----------------
    c = "c_005"
    b.customer(c, "Yasmine El Idrissi", "Yasmine", 23, "salariée", "single", "Bruxelles", "fr", "high", 1400.0,
               "Premier emploi", "yasmine")
    for (y, m) in full[:-1]:
        b.t(c, d(y, m, 28), 780, "student_job", "Job étudiant", "Agence intérim")
    b.t(c, "2026-09-25", 2150, "salary", "Salaire", "Startup SRL")
    b.monthly(c, 3, -550, "rent", "Kot / loyer", "Propriétaire")
    b.monthly(c, 15, -25, "telecom", "Télécom", "Opérateur")
    b.groceries(c, 45)
    for i in range(5):
        b.ev(c, NOW - timedelta(days=i, hours=5), "home")
    b.products += [(c, "student_account", "Compte jeune", None)]

    # ---------------- Thomas : rien à signaler -> S'ABSTENIR ----------------
    c = "c_006"
    b.customer(c, "Thomas Verbeke", "Thomas", 45, "salarié", "family", "Wavre", "fr", "medium", 9000.0,
               "Situation stable, rien à proposer", "thomas")
    b.monthly(c, 25, 3800, "salary", "Salaire", "Employeur NV", full)
    b.monthly(c, 2, -1200, "mortgage_payment", "Prêt hypothécaire", "Banque")
    b.monthly(c, 10, -210, "utilities", "Énergie", "Fournisseur énergie")
    b.monthly(c, 26, -400, "savings_transfer", "Épargne", "Compte épargne", full)
    b.groceries(c, 150)
    b.t(c, "2026-09-07", -50.0, "religious_donation", "Don", "Association")                  # exclue (art. 9)
    b.t(c, "2026-09-16", -18.7, "pharmacy", "Pharmacie", "Pharmacie")                        # exclue (art. 9)
    b.ev(c, NOW - timedelta(days=2), "home")
    b.products += [(c, "current_account", "", None), (c, "savings", "", None),
                   (c, "mortgage_fixed_rate", "Taux fixe 10 ans", "2027-06-30"), (c, "car_insurance", "", "2026-12-15")]

    # ---------------- Nina : simulation de prêt abandonnée -> SIMPLIFIER (crédit = humain) ----------------
    c = "c_007"
    b.customer(c, "Nina Haddad", "Nina", 29, "salariée", "couple", "Mons", "fr", "high", 18000.0,
               "Projet d'achat, simulation abandonnée", "nina")
    b.monthly(c, 25, 2900, "salary", "Salaire", "Employeur SA", full)
    b.monthly(c, 3, -900, "rent", "Loyer", "Propriétaire")
    b.monthly(c, 26, -700, "savings_transfer", "Épargne apport", "Compte épargne", full)
    b.groceries(c, 90)
    b.ev(c, NOW - timedelta(days=6), "sim_loan", "start")
    b.ev(c, NOW - timedelta(days=6, minutes=-12), "sim_loan", "abandon")
    for i in range(4):
        b.ev(c, NOW - timedelta(days=i + 1, hours=3), "loan_info")
    b.ev(c, NOW - timedelta(hours=20), "home")
    b.products += [(c, "current_account", "", None), (c, "savings", "", None)]

    b.users.append(("conseiller", "advisor", None))
    return b


def write(b: Builder, db_path: Path | None = None) -> dict[str, str]:
    path = db_path or settings.db_path
    if path.exists():
        path.unlink()
    init_db(path)
    shared = os.getenv("DEMO_PASSWORD", "")
    creds: dict[str, str] = {}
    with get_conn(path) as conn:
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)", b.customers)
        conn.executemany("INSERT INTO transactions(customer_id,date,amount,category,label,counterparty) VALUES (?,?,?,?,?,?)", b.tx)
        conn.executemany("INSERT INTO app_events(customer_id,ts,screen,action) VALUES (?,?,?,?)", b.events)
        conn.executemany("INSERT INTO products(customer_id,product_type,detail,end_date) VALUES (?,?,?,?)", b.products)
        conn.executemany("INSERT INTO pending_transfers(customer_id,created_at,amount,beneficiary,beneficiary_is_new,beneficiary_type) VALUES (?,?,?,?,?,?)", b.pending)
        for username, role, cid in b.users:
            pwd = shared or secrets.token_urlsafe(9)
            creds[username] = pwd
            conn.execute("INSERT INTO users VALUES (?,?,?,?)", (username, hash_password(pwd), role, cid))
    return creds


def main() -> None:
    b = build()
    creds = write(b)
    out = ROOT / ".demo_credentials"          # ignoré par git
    out.write_text("\n".join(f"{u}: {p}" for u, p in creds.items()) + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    print(f"Base créée : {settings.db_path}")
    print(f"{len(b.customers)} clients, {len(b.tx)} transactions, {len(b.events)} événements app")
    print(f"Identifiants de démo écrits dans {out.name} (non versionné) :")
    for u, p in creds.items():
        print(f"  {u:<11} {p}")


if __name__ == "__main__":
    main()
