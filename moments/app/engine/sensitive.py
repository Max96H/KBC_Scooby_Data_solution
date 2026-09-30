"""Filtre RGPD art. 9 : appliqué à l'ingestion, AVANT tout calcul de signal.

Ces transactions ne sont jamais lues par le moteur. On ne garde que leur nombre,
pour pouvoir montrer (dans la démo et dans le panneau « pourquoi ») qu'elles ont été exclues.
"""
from __future__ import annotations

# Catégories dont on pourrait inférer : santé, religion, opinions politiques,
# appartenance syndicale, vie sexuelle / orientation.
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
    """Retourne (transactions utilisables, nombre de transactions exclues)."""
    kept = [t for t in transactions if t["category"] not in SENSITIVE_CATEGORIES]
    return kept, len(transactions) - len(kept)
