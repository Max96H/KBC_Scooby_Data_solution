"""GDPR art. 9 filter: applied at ingestion, BEFORE any signal is computed.

These transactions are never read by the engine. Only their count is kept, so that the demo
(and the "why am I seeing this" panel) can show that they were excluded.
"""
from __future__ import annotations

# Categories that could reveal health, religion, political opinions,
# trade-union membership, sex life or sexual orientation.
SENSITIVE_CATEGORIES: frozenset[str] = frozenset({
    "pharmacy",
    "medical",
    "hospital",
    "mental_health",
    "religious_donation",
    "place_of_worship",
    "political_party",
    "trade_union",
    "dating",
    "lgbtq_association",
})


def split_sensitive(transactions: list[dict]) -> tuple[list[dict], int]:
    """Return (usable transactions, number of excluded transactions)."""
    kept = [t for t in transactions if t["category"] not in SENSITIVE_CATEGORIES]
    return kept, len(transactions) - len(kept)
