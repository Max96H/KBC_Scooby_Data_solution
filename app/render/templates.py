"""Fallback templates: used when no LLM is configured, on error, or when the LLM output fails
validation. The product therefore always works, with or without generative AI.
"""
from __future__ import annotations

from app.engine.catalog import CATALOG
from app.i18n import ABSTAIN_COPY, ACCOMPANY_INTRO, CHECKLISTS, WARM_INTRO, norm_lang, pick


def template_copy(action_id: str, language: str, variant: str) -> dict:
    lang = norm_lang(language)
    if action_id == "abstain":
        c = ABSTAIN_COPY[lang]
        return {"title": c["title"], "body": c["body"], "push": "", "checklist_title": "", "checklist": []}
    action = CATALOG[action_id]
    copy = action.copy.get(lang) or action.copy["en"]
    body = copy["body"]
    if variant == "warm":
        intro = pick(ACCOMPANY_INTRO, lang) if action.family == "accompany" else WARM_INTRO[lang].get(action.moment, "")
        body = intro + body
    checklist_title, checklist = CHECKLISTS.get(action_id, {}).get(lang, ("", []))
    return {"title": copy["title"], "body": body, "push": copy["push"],
            "checklist_title": checklist_title, "checklist": list(checklist)}
