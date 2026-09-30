"""Contrat de sortie du LLM. Le LLM ne produit QUE du texte dans des champs typés et bornés.

La structure de l'écran (types de blocs, boutons, panneau « pourquoi ») est assemblée par le serveur.
Conséquence : le LLM ne peut ni injecter du HTML / du code, ni inventer un bouton, ni mentir sur les
signaux utilisés (le panneau « pourquoi » est construit à partir du journal du moteur, pas par le LLM).
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Interdit : balises, URL, pseudo-protocoles, gabarits autres que {first_name}, caractères de contrôle
_FORBIDDEN = re.compile(r"[<>]|https?://|www\.|javascript:|data:|\{(?!first_name\})|[\x00-\x08\x0b\x0c\x0e-\x1f]", re.I)
# Interdit dans une promesse commerciale générée : chiffres de taux / montants inventés
_FIGURES = re.compile(r"\d+([.,]\d+)?\s?(%|€|eur)", re.I)


def _clean(value: str, allow_figures: bool = False) -> str:
    value = value.strip()
    if _FORBIDDEN.search(value):
        raise ValueError("contenu interdit (HTML, URL ou gabarit)")
    if not allow_figures and _FIGURES.search(value):
        raise ValueError("le LLM ne doit pas inventer de chiffres (taux, montants)")
    return value


class LlmCopy(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    body: str = Field(min_length=10, max_length=420)
    checklist_title: str = Field(default="", max_length=60)
    checklist: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("title", "body", "checklist_title")
    @classmethod
    def _text(cls, v: str) -> str:
        return _clean(v) if v else v

    @field_validator("checklist")
    @classmethod
    def _items(cls, v: list[str]) -> list[str]:
        out = []
        for item in v:
            if len(item) > 140:
                raise ValueError("élément de liste trop long")
            out.append(_clean(item, allow_figures=True))  # la règle 50/30/20 contient des pourcentages connus
        return out


# Schéma transmis à Gemini (responseSchema, sous-ensemble OpenAPI)
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "body": {"type": "STRING"},
        "checklist_title": {"type": "STRING"},
        "checklist": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["title", "body"],
}

# Types de blocs que le front sait afficher. Tout autre type est ignoré par le front.
BLOCK_TYPES = {"highlight", "checklist", "why_panel", "transfer_hold", "voice", "human", "abstain"}
