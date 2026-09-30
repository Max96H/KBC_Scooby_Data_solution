"""Output contract of the LLM. The LLM ONLY produces text inside typed, bounded fields.

The screen structure (block types, buttons, "why" panel) is assembled by the server.
Consequence: the LLM can neither inject HTML / code, nor invent a button, nor lie about the
signals used (the "why" panel is built from the engine journal, not by the LLM).
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Forbidden: tags, URLs, pseudo-protocols, templates other than {first_name}, control characters
_FORBIDDEN = re.compile(r"[<>]|https?://|www\.|javascript:|data:|\{(?!first_name\})|[\x00-\x08\x0b\x0c\x0e-\x1f]", re.I)
# Forbidden in a generated commercial message: invented figures (rates, amounts)
_FIGURES = re.compile(r"\d+([.,]\d+)?\s?(%|€|eur|\$)", re.I)


def _clean(value: str, allow_figures: bool = False) -> str:
    value = value.strip()
    if _FORBIDDEN.search(value):
        raise ValueError("forbidden content (HTML, URL or template)")
    if not allow_figures and _FIGURES.search(value):
        raise ValueError("the LLM must not invent figures (rates, amounts)")
    return value


class LlmCopy(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    body: str = Field(min_length=10, max_length=420)
    push: str = Field(default="", max_length=110)
    checklist_title: str = Field(default="", max_length=60)
    checklist: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("title", "body", "push", "checklist_title")
    @classmethod
    def _text(cls, v: str) -> str:
        return _clean(v) if v else v

    @field_validator("checklist")
    @classmethod
    def _items(cls, v: list[str]) -> list[str]:
        out = []
        for item in v:
            if len(item) > 140:
                raise ValueError("list item too long")
            out.append(_clean(item, allow_figures=True))  # the 50/30/20 rule contains known percentages
        return out


# Schema sent to Gemini (responseSchema, OpenAPI subset)
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "body": {"type": "STRING"},
        "push": {"type": "STRING"},
        "checklist_title": {"type": "STRING"},
        "checklist": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["title", "body"],
}

# Block types the front end knows how to display. Any other type is ignored by the front end.
BLOCK_TYPES = {"highlight", "checklist", "why_panel", "transfer_hold", "human", "abstain"}
