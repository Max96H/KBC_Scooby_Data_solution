"""Accès SQLite. Toutes les requêtes sont paramétrées (pas de concaténation SQL)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    status TEXT NOT NULL,            -- salarié, étudiant, retraité, indépendant
    household TEXT NOT NULL,         -- single, couple, family, couple_senior
    city TEXT NOT NULL,
    language TEXT NOT NULL,          -- fr, nl
    digital_level TEXT NOT NULL,     -- high, medium, low
    opening_balance REAL NOT NULL,
    persona TEXT NOT NULL            -- libellé de démo
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,            -- négatif = débit
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    counterparty TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tx_customer ON transactions(customer_id, date);

CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    ts TEXT NOT NULL,
    screen TEXT NOT NULL,
    action TEXT NOT NULL             -- view, start, abandon, complete
);
CREATE INDEX IF NOT EXISTS idx_ev_customer ON app_events(customer_id, ts);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    product_type TEXT NOT NULL,      -- current_account, savings, mortgage, home_insurance, car_insurance, family_insurance, student_account, pension_savings
    detail TEXT NOT NULL DEFAULT '',
    end_date TEXT
);

CREATE TABLE IF NOT EXISTS pending_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    created_at TEXT NOT NULL,
    amount REAL NOT NULL,
    beneficiary TEXT NOT NULL,
    beneficiary_is_new INTEGER NOT NULL,
    beneficiary_type TEXT NOT NULL,  -- person, merchant, crypto_platform
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, held, confirmed, cancelled
    hold_until TEXT
);

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('customer', 'advisor')),
    customer_id TEXT REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS consents (
    customer_id TEXT NOT NULL REFERENCES customers(id),
    family TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (customer_id, family)
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    created_at TEXT NOT NULL,
    action_id TEXT NOT NULL,         -- 'abstain' si le moteur s'abstient
    action_family TEXT NOT NULL,
    channel TEXT NOT NULL,
    score REAL NOT NULL,
    variant TEXT NOT NULL,
    journal_json TEXT NOT NULL,
    screen_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dec_customer ON decisions(customer_id, created_at);

-- Boucle de feedback : identifiant pseudonymisé, aucune donnée transactionnelle.
CREATE TABLE IF NOT EXISTS action_events (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(id),
    customer_ref TEXT NOT NULL,
    action_id TEXT NOT NULL,
    segment TEXT NOT NULL,
    channel TEXT NOT NULL,
    variant TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    reaction TEXT NOT NULL DEFAULT 'ignored',
    reaction_at TEXT,
    why_opened INTEGER NOT NULL DEFAULT 0,
    simulated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ae_action ON action_events(action_id, segment, sent_at);

CREATE TABLE IF NOT EXISTS suppressions (
    customer_ref TEXT NOT NULL,
    action_id TEXT NOT NULL,
    until TEXT NOT NULL,             -- '9999-12-31' = définitif
    reason TEXT NOT NULL,
    PRIMARY KEY (customer_ref, action_id)
);

CREATE TABLE IF NOT EXISTS advisor_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    decision_id TEXT REFERENCES decisions(id),
    action_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',      -- open, done
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS render_cache (
    cache_key TEXT PRIMARY KEY,
    screen_json TEXT NOT NULL,
    source TEXT NOT NULL,            -- llm, template
    created_at TEXT NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or settings.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with get_conn(path) as conn:
        conn.executescript(SCHEMA)
