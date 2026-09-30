"""Gabarits de repli : utilisés quand aucun LLM n'est configuré, en cas d'erreur, ou si la sortie du LLM
échoue à la validation. Le produit fonctionne donc toujours, avec ou sans IA générative.
"""
from __future__ import annotations

from app.engine.catalog import ABSTAIN_COPY, CATALOG, WARM_INTRO

# Dans un moment difficile, pas de « félicitations » : un ton chaleureux mais sobre
ACCOMPANY_INTRO = {"fr": "Nous pensons à vous en ce moment. ", "nl": "We denken in deze periode aan u. "}

CHECKLISTS: dict[str, dict[str, tuple[str, list[str]]]] = {
    "first_salary_budget": {
        "fr": ("La règle 50/30/20", ["50 % : loyer, courses, transport", "30 % : sorties, loisirs, envies", "20 % : épargne, versée automatiquement le jour du salaire"]),
        "nl": ("De 50/30/20-regel", ["50 %: huur, boodschappen, vervoer", "30 %: uitgaan, hobby's", "20 %: sparen, automatisch op loondag"]),
    },
    "family_budget_support": {
        "fr": ("Ce que votre budget prévisionnel contient", ["Les nouvelles dépenses liées à l'enfant, mois par mois", "Les allocations familiales auxquelles vous avez droit", "Les paiements qui peuvent être étalés sans frais"]),
        "nl": ("Wat uw budgetplanning bevat", ["De nieuwe kosten voor het kind, maand per maand", "Het groeipakket waar u recht op hebt", "Betalingen die zonder kosten gespreid kunnen worden"]),
    },
    "scam_pause": {
        "fr": ("Comment reconnaître une arnaque", ["On vous presse d'agir tout de suite", "Quelqu'un vous demande de « sécuriser » votre argent", "On vous demande de garder le secret, même envers vos proches"]),
        "nl": ("Hoe herkent u oplichting", ["Men zet u onder druk om meteen te handelen", "Iemand vraagt u uw geld te 'beveiligen'", "Men vraagt u het geheim te houden, zelfs voor uw naasten"]),
    },
    "grandchild_savings_info": {
        "fr": ("Bon à savoir", ["Une épargne peut être ouverte au nom de l'enfant", "La donation bancaire doit respecter certaines règles fiscales", "Un conseiller vous explique tout, sans engagement"]),
        "nl": ("Goed om te weten", ["Er kan een spaarrekening op naam van het kind worden geopend", "Een bankschenking moet bepaalde fiscale regels volgen", "Een adviseur legt alles vrijblijvend uit"]),
    },
}


def template_copy(action_id: str, language: str, variant: str) -> dict:
    lang = language if language in ("fr", "nl") else "fr"
    if action_id == "abstain":
        c = ABSTAIN_COPY[lang]
        return {"title": c["title"], "body": c["body"], "checklist_title": "", "checklist": []}
    action = CATALOG[action_id]
    copy = action.copy.get(lang) or action.copy["fr"]
    body = copy["body"]
    if variant == "warm":
        intro = ACCOMPANY_INTRO[lang] if action.family == "accompany" else WARM_INTRO[lang].get(action.moment, "")
        body = intro + body
    title = copy["title"]
    checklist_title, checklist = CHECKLISTS.get(action_id, {}).get(lang, ("", []))
    return {"title": title, "body": body, "checklist_title": checklist_title, "checklist": list(checklist)}
