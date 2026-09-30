"""Server-side customer-facing strings in English, French and Dutch.

Only text the CUSTOMER reads lives here (message cards, evidence, "why am I seeing this", confirmations).
Interface labels (buttons, journal, advisor console) are translated in the front end (static/i18n.js).
"""
from __future__ import annotations

from app.config import LANGUAGES

L = dict[str, str]


def pick(texts: L, lang: str) -> str:
    """Return the text in the requested language, falling back to English."""
    return texts.get(lang) or texts["en"]


def norm_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else "en"


# --------------------------------------------------------------------------- evidence (why panel)
EVIDENCE: dict[str, L] = {
    "baby_purchases": {"en": "Recent purchases in baby stores", "fr": "Achats récents dans des magasins pour bébé", "nl": "Recente aankopen in babywinkels"},
    "sim_family_insurance": {"en": "Family insurance simulation started in the app", "fr": "Simulation « assurance famille » commencée dans l'app", "nl": "Simulatie 'gezinsverzekering' gestart in de app"},
    "household_young": {"en": "Profile: household aged 22 to 45", "fr": "Profil : ménage de 22 à 45 ans", "nl": "Profiel: gezin van 22 tot 45 jaar"},
    "birth_gift": {"en": "Transfer mentioning a birth", "fr": "Virement avec la mention « naissance »", "nl": "Overschrijving met vermelding 'geboorte'"},
    "recurring_family_transfer": {"en": "Regular monthly transfer to a relative", "fr": "Virement mensuel régulier vers un proche", "nl": "Regelmatige maandelijkse overschrijving naar een naaste"},
    "age_55_plus": {"en": "Profile: aged 55 or over", "fr": "Profil : 55 ans et plus", "nl": "Profiel: 55 jaar en ouder"},
    "first_salary": {"en": "First salary received this month", "fr": "Premier salaire reçu ce mois-ci", "nl": "Eerste loon deze maand ontvangen"},
    "student_account": {"en": "You still have a student account", "fr": "Vous avez encore un compte étudiant", "nl": "U hebt nog een studentenrekening"},
    "balance_down_3m": {"en": "Balance going down for 3 months", "fr": "Solde en baisse depuis 3 mois", "nl": "Saldo daalt al 3 maanden"},
    "savings_down": {"en": "Monthly savings decreasing", "fr": "Épargne mensuelle en diminution", "nl": "Maandelijks sparen neemt af"},
    "late_fees": {"en": "Several recent late-payment fees", "fr": "Plusieurs frais de retard récents", "nl": "Meerdere recente aanmaningskosten"},
    "overdraft_forecast": {"en": "Scheduled payments exceed your balance within 7 days", "fr": "Paiements prévus supérieurs au solde dans les 7 jours", "nl": "Geplande betalingen hoger dan het saldo binnen 7 dagen"},
    "salary_missing": {"en": "Usual income not received this month", "fr": "Revenu habituel absent ce mois-ci", "nl": "Gebruikelijk inkomen deze maand niet ontvangen"},
    "new_beneficiary": {"en": "Beneficiary never paid before", "fr": "Bénéficiaire jamais payé auparavant", "nl": "Begunstigde nooit eerder betaald"},
    "unusual_amount": {"en": "Unusual amount for this account", "fr": "Montant inhabituel pour ce compte", "nl": "Ongewoon bedrag voor deze rekening"},
    "crypto_platform": {"en": "First transfer to a crypto platform", "fr": "Premier virement vers une plateforme crypto", "nl": "Eerste overschrijving naar een cryptoplatform"},
    "senior_security": {"en": "Profile more exposed to scams (fraud prevention)", "fr": "Profil plus exposé aux arnaques (prévention fraude)", "nl": "Profiel meer blootgesteld aan oplichting (fraudepreventie)"},
    "sim_loan_abandoned": {"en": "Home loan simulation started then abandoned", "fr": "Simulation de prêt logement commencée puis abandonnée", "nl": "Simulatie woonkrediet gestart en onderbroken"},
    "loan_pages": {"en": "Home loan pages viewed several times", "fr": "Pages « crédit logement » consultées plusieurs fois", "nl": "Pagina's 'woonkrediet' meerdere keren bekeken"},
    "housing_costs": {"en": "Recent notary or moving costs", "fr": "Frais de notaire ou de déménagement récents", "nl": "Recente notaris- of verhuiskosten"},
    "fixed_rate_end": {"en": "Your fixed rate ends in less than 4 months", "fr": "Fin de votre taux fixe dans moins de 4 mois", "nl": "Einde van uw vaste rentevoet binnen 4 maanden"},
    "car_renewal": {"en": "Car insurance renewal within a month", "fr": "Assurance auto à renouveler dans le mois", "nl": "Autoverzekering te verlengen binnen de maand"},
    "pension_room": {"en": "Pension savings held, end of tax year approaching", "fr": "Épargne-pension détenue, fin d'année fiscale proche", "nl": "Pensioensparen aanwezig, einde van het fiscale jaar nadert"},
    "retirement_age": {"en": "Profile: aged 60 to 66, loan ending soon", "fr": "Profil : 60 à 66 ans, crédit bientôt terminé", "nl": "Profiel: 60 tot 66 jaar, krediet bijna afgelopen"},
}

# --------------------------------------------------------------------------- why panel and blocks
UI: dict[str, L] = {
    "why_title": {"en": "Why am I seeing this?", "fr": "Pourquoi je vois ça ?", "nl": "Waarom zie ik dit?"},
    "excluded": {"en": "{n} transaction(s) related to health or beliefs were excluded and are never analysed.",
                 "fr": "{n} transaction(s) liées à la santé ou à des convictions ont été exclues et ne sont jamais analysées.",
                 "nl": "{n} transactie(s) over gezondheid of overtuigingen werden uitgesloten en worden nooit geanalyseerd."},
    "fraud_basis": {"en": "Legal basis: fraud prevention (cannot be switched off).",
                    "fr": "Base légale : prévention de la fraude (non désactivable).",
                    "nl": "Rechtsgrond: fraudepreventie (niet uit te schakelen)."},
    "consent_basis": {"en": "Based on the data you allowed. You can switch it off at any time.",
                      "fr": "Basé sur les données que vous avez autorisées. Vous pouvez les couper à tout moment.",
                      "nl": "Gebaseerd op de gegevens die u toestond. U kunt ze op elk moment uitschakelen."},
    "credit_human": {"en": "No credit decision is automatic: a person always reviews it.",
                     "fr": "Aucune décision de crédit n'est automatique : une personne l'examine toujours.",
                     "nl": "Geen enkele kredietbeslissing is automatisch: een mens bekijkt ze altijd."},
    "human_title": {"en": "Talk it through with an advisor", "fr": "En parler avec un conseiller", "nl": "Erover praten met een adviseur"},
    "human_body": {"en": "This deserves a real conversation. Pick a time that suits you: by phone, video or in a branch.",
                   "fr": "Ce sujet mérite une vraie conversation. Choisissez un moment qui vous convient : par téléphone, en vidéo ou en agence.",
                   "nl": "Dit verdient een echt gesprek. Kies een moment dat u past: telefonisch, via video of in een kantoor."},
}

# --------------------------------------------------------------------------- confirmations after a button
MESSAGES: dict[str, L] = {
    "complete": {"en": "Done. (Demo: the action is simulated.)", "fr": "C'est fait. (Démo : l'action est simulée.)", "nl": "Klaar. (Demo: de actie is gesimuleerd.)"},
    "ack": {"en": "Thanks, there is more information below.", "fr": "Merci, vous trouverez plus d'informations ci-dessous.", "nl": "Bedankt, hieronder leest u meer."},
    "book": {"en": "Choose a time for your appointment.", "fr": "Choisissez un moment pour votre rendez-vous.", "nl": "Kies een moment voor uw afspraak."},
    "callback": {"en": "An advisor will call you back. Nothing is decided without you.",
                 "fr": "Un conseiller vous rappelle. Rien n'est décidé sans vous.",
                 "nl": "Een adviseur belt u terug. Er wordt niets beslist zonder u."},
    "fraud_call": {"en": "Our fraud team will call you right away.", "fr": "Notre équipe anti-fraude vous appelle tout de suite.", "nl": "Ons fraudeteam belt u meteen."},
    "cancel_transfer": {"en": "Transfer cancelled. Your money has not moved.", "fr": "Virement annulé. Votre argent n'a pas bougé.", "nl": "Overschrijving geannuleerd. Uw geld is niet verplaatst."},
    "confirm_transfer": {"en": "Transfer confirmed and executed.", "fr": "Virement confirmé et exécuté.", "nl": "Overschrijving bevestigd en uitgevoerd."},
    "booked": {"en": "Appointment booked. You will find it under Appointments.", "fr": "Rendez-vous réservé. Vous le retrouvez dans l'onglet Rendez-vous.", "nl": "Afspraak geboekt. U vindt ze onder Afspraken."},
    "cancelled": {"en": "Appointment cancelled.", "fr": "Rendez-vous annulé.", "nl": "Afspraak geannuleerd."},
}

# --------------------------------------------------------------------------- abstention
ABSTAIN_COPY: dict[str, dict[str, str]] = {
    "en": {"title": "Nothing for you today", "body": "We have nothing useful to suggest right now, so we'd rather not disturb you."},
    "fr": {"title": "Aucune proposition aujourd'hui", "body": "Nous n'avons rien d'utile à vous proposer en ce moment, alors nous préférons ne pas vous déranger."},
    "nl": {"title": "Vandaag geen voorstel", "body": "We hebben op dit moment niets nuttigs voor u, dus we storen u liever niet."},
}

ABSTAIN_REASON: dict[str, L] = {
    "no_signal": {"en": "Nothing in your current situation justifies contacting you.",
                  "fr": "Rien dans votre situation actuelle ne justifie de vous solliciter.",
                  "nl": "Niets in uw huidige situatie rechtvaardigt dat we u contacteren."},
    "low_confidence": {"en": "We are not sure enough about what you need, so we assume nothing.",
                       "fr": "Nous ne sommes pas assez sûrs de ce dont vous avez besoin, donc nous ne supposons rien.",
                       "nl": "We zijn niet zeker genoeg van wat u nodig hebt, dus we veronderstellen niets."},
    "stress_no_sales": {"en": "All commercial offers are switched off for you at the moment.",
                        "fr": "Toutes les offres commerciales sont désactivées pour vous en ce moment.",
                        "nl": "Alle commerciële aanbiedingen staan voor u momenteel uit."},
    "all_blocked": {"en": "You told us you don't want this kind of message, and we respect that.",
                    "fr": "Vous nous avez indiqué ne pas vouloir ce type de message, et nous le respectons.",
                    "nl": "U gaf aan dit soort berichten niet te willen, en dat respecteren we."},
}

# --------------------------------------------------------------------------- tone variants (tested by the bandit)
WARM_INTRO: dict[str, dict[str, str]] = {
    "en": {"baby": "Congratulations on the lovely news! ", "grandchild": "What lovely news in your family! ",
           "first_job": "Well done on your first salary! ", "fraud": "We would rather check this with you. ",
           "financial_stress": "We are keeping an eye on your account for you. ", "housing": "A home project is a big step. "},
    "fr": {"baby": "Félicitations pour cette belle nouvelle ! ", "grandchild": "Quelle belle nouvelle dans votre famille ! ",
           "first_job": "Bravo pour ce premier salaire ! ", "fraud": "Nous préférons vérifier avec vous. ",
           "financial_stress": "Nous gardons un œil sur votre compte pour vous. ", "housing": "Un projet de logement, c'est une grande étape. "},
    "nl": {"baby": "Proficiat met dit mooie nieuws! ", "grandchild": "Wat een mooi nieuws in uw familie! ",
           "first_job": "Proficiat met uw eerste loon! ", "fraud": "We kijken dit liever samen met u na. ",
           "financial_stress": "We houden uw rekening voor u in de gaten. ", "housing": "Een woonproject is een grote stap. "},
}
# In a difficult moment: no "congratulations", warm but sober
ACCOMPANY_INTRO: L = {"en": "We are thinking of you at the moment. ", "fr": "Nous pensons à vous en ce moment. ", "nl": "We denken in deze periode aan u. "}

# --------------------------------------------------------------------------- checklists
CHECKLISTS: dict[str, dict[str, tuple[str, list[str]]]] = {
    "first_salary_budget": {
        "en": ("The 50/30/20 rule", ["50%: rent, groceries, transport", "30%: going out, hobbies, treats", "20%: savings, moved automatically on payday"]),
        "fr": ("La règle 50/30/20", ["50 % : loyer, courses, transport", "30 % : sorties, loisirs, envies", "20 % : épargne, versée automatiquement le jour du salaire"]),
        "nl": ("De 50/30/20-regel", ["50%: huur, boodschappen, vervoer", "30%: uitgaan, hobby's", "20%: sparen, automatisch op loondag"]),
    },
    "family_budget_support": {
        "en": ("What your budget plan contains", ["The new costs linked to your child, month by month", "The family allowances you are entitled to", "Payments that can be spread at no cost"]),
        "fr": ("Ce que votre budget prévisionnel contient", ["Les nouvelles dépenses liées à l'enfant, mois par mois", "Les allocations familiales auxquelles vous avez droit", "Les paiements qui peuvent être étalés sans frais"]),
        "nl": ("Wat uw budgetplanning bevat", ["De nieuwe kosten voor het kind, maand per maand", "Het groeipakket waar u recht op hebt", "Betalingen die zonder kosten gespreid kunnen worden"]),
    },
    "scam_pause": {
        "en": ("How to recognise a scam", ["You are pushed to act right now", "Someone asks you to 'secure' your money", "You are asked to keep it secret, even from your family"]),
        "fr": ("Comment reconnaître une arnaque", ["On vous presse d'agir tout de suite", "Quelqu'un vous demande de « sécuriser » votre argent", "On vous demande de garder le secret, même envers vos proches"]),
        "nl": ("Hoe herkent u oplichting", ["Men zet u onder druk om meteen te handelen", "Iemand vraagt u uw geld te 'beveiligen'", "Men vraagt u het geheim te houden, zelfs voor uw naasten"]),
    },
    "grandchild_savings_info": {
        "en": ("Good to know", ["Savings can be opened in the child's name", "A bank gift must follow some tax rules", "An advisor explains everything, with no obligation"]),
        "fr": ("Bon à savoir", ["Une épargne peut être ouverte au nom de l'enfant", "La donation bancaire doit respecter certaines règles fiscales", "Un conseiller vous explique tout, sans engagement"]),
        "nl": ("Goed om te weten", ["Er kan een spaarrekening op naam van het kind worden geopend", "Een bankschenking moet bepaalde fiscale regels volgen", "Een adviseur legt alles vrijblijvend uit"]),
    },
    "overdraft_alert": {
        "en": ("Scheduled in the next 7 days", ["Rent", "Utilities", "You can move a non-urgent payment by a few days"]),
        "fr": ("Prévu dans les 7 prochains jours", ["Loyer", "Énergie", "Vous pouvez décaler un paiement non urgent de quelques jours"]),
        "nl": ("Gepland in de komende 7 dagen", ["Huur", "Energie", "U kunt een niet-dringende betaling enkele dagen verschuiven"]),
    },
}
