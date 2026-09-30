"""Catalogue d'actions : la seule liste d'actions que le moteur (et donc le client) peut déclencher.

Toute action_id reçue de l'extérieur est validée contre ce catalogue côté serveur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Les 6 familles d'actions (annexe A du document de décisions)
FAMILIES = {
    "inform": "Informer",
    "protect": "Protéger",
    "simplify": "Simplifier",
    "propose": "Proposer",
    "accompany": "Accompagner",
    "abstain": "S'abstenir",
}


@dataclass(frozen=True)
class Cta:
    id: str
    label: dict[str, str]           # {"fr": ..., "nl": ...}
    effect: str                      # ce que le serveur fait quand le client clique


@dataclass(frozen=True)
class Action:
    id: str
    family: str
    moment: str
    product: str
    value_customer: float
    value_bank: float
    sensitivity: float
    urgency: float
    is_commercial: bool
    ctas: tuple[Cta, ...]
    copy: dict[str, dict[str, str]]  # langue -> {title, body}
    legal_basis: str = "consent"     # consent | fraud_prevention
    sensitive_topic: bool = False    # stress, deuil, arnaque complexe -> humain
    involves_credit: bool = False    # RGPD art. 22 : jamais de décision automatique
    variants: tuple[str, ...] = ("warm", "direct")


def _cta(id_: str, fr: str, nl: str, effect: str) -> Cta:
    return Cta(id=id_, label={"fr": fr, "nl": nl}, effect=effect)


BOOK = _cta("book_appointment", "Prendre rendez-vous avec un conseiller", "Afspraak maken met een adviseur", "advisor_task")
LEARN = _cta("learn_more", "En savoir plus", "Meer weten", "ack")

CATALOG: dict[str, Action] = {
    a.id: a
    for a in [
        Action(
            id="family_insurance_review", family="propose", moment="baby", product="assurance famille + épargne enfant",
            value_customer=0.8, value_bank=0.5, sensitivity=0.3, urgency=0.6, is_commercial=True,
            ctas=(
                _cta("start_review", "Revoir ma couverture (2 min)", "Mijn dekking nakijken (2 min)", "complete"),
                _cta("open_child_savings", "Ouvrir une épargne enfant", "Kinderspaarrekening openen", "complete"),
                BOOK,
            ),
            copy={
                "fr": {"title": "Un nouveau membre dans la famille ?",
                       "body": "Votre assurance familiale couvre-t-elle déjà votre enfant ? Vérifiez en deux minutes, et découvrez comment commencer une épargne pour lui dès aujourd'hui."},
                "nl": {"title": "Een nieuw gezinslid?",
                       "body": "Is uw kind al gedekt door uw gezinsverzekering? Controleer het in twee minuten en ontdek hoe u vandaag al voor hem of haar kunt sparen."},
            },
        ),
        Action(
            id="family_budget_support", family="accompany", moment="baby", product="accompagnement budgétaire",
            value_customer=0.95, value_bank=0.1, sensitivity=0.6, urgency=0.85, is_commercial=False, sensitive_topic=True,
            ctas=(
                BOOK,
                _cta("open_budget_plan", "Voir mon budget prévisionnel", "Mijn budgetplanning bekijken", "complete"),
            ),
            copy={
                "fr": {"title": "Un budget qui suit votre nouvelle vie",
                       "body": "L'arrivée d'un enfant change beaucoup de choses. Nous avons préparé un budget prévisionnel pour les prochains mois, et un conseiller peut le revoir avec vous, sans engagement et sans aucune offre commerciale."},
                "nl": {"title": "Een budget dat met uw nieuwe leven meegaat",
                       "body": "De komst van een kind verandert veel. We hebben een budgetplanning voor de komende maanden voorbereid en een adviseur kan die vrijblijvend met u overlopen, zonder commercieel aanbod."},
            },
        ),
        Action(
            id="grandchild_savings_info", family="inform", moment="grandchild", product="donation / épargne petit-enfant",
            value_customer=0.7, value_bank=0.3, sensitivity=0.3, urgency=0.35, is_commercial=False,
            ctas=(
                _cta("callback_request", "Être rappelé par un conseiller", "Teruggebeld worden door een adviseur", "advisor_task"),
                LEARN,
            ),
            copy={
                "fr": {"title": "Aider un petit-enfant, en toute sérénité",
                       "body": "Vous soutenez un jeune parent de votre famille. Saviez-vous qu'il existe des façons simples d'épargner pour un petit-enfant, et que la donation bancaire a des règles fiscales à connaître ? Un conseiller peut vous les expliquer."},
                "nl": {"title": "Een kleinkind helpen, met een gerust gevoel",
                       "body": "U steunt een jonge ouder in uw familie. Wist u dat er eenvoudige manieren zijn om voor een kleinkind te sparen, en dat een bankschenking fiscale regels heeft die u best kent? Een adviseur legt het u graag uit."},
            },
        ),
        Action(
            id="scam_pause", family="protect", moment="fraud", product="protection anti-arnaque",
            value_customer=1.0, value_bank=0.2, sensitivity=0.2, urgency=1.0, is_commercial=False, legal_basis="fraud_prevention",
            ctas=(
                _cta("cancel_transfer", "Annuler ce virement", "Deze overschrijving annuleren", "cancel_transfer"),
                _cta("confirm_transfer", "Je connais ce bénéficiaire, confirmer", "Ik ken deze begunstigde, bevestigen", "confirm_transfer"),
                _cta("call_bank", "Parler à quelqu'un maintenant", "Nu met iemand praten", "advisor_task"),
            ),
            copy={
                "fr": {"title": "Pause de sécurité de 10 minutes",
                       "body": "Ce virement va vers un bénéficiaire que vous n'avez jamais payé, pour un montant inhabituel. Les arnaqueurs se font souvent passer pour la banque ou un service technique et pressent leurs victimes. Prenez 10 minutes : personne de la banque ne vous demandera jamais de déplacer votre argent."},
                "nl": {"title": "Veiligheidspauze van 10 minuten",
                       "body": "Deze overschrijving gaat naar een begunstigde die u nog nooit betaalde, voor een ongewoon bedrag. Oplichters doen zich vaak voor als de bank of een technische dienst en zetten hun slachtoffers onder druk. Neem 10 minuten: niemand van de bank zal u ooit vragen uw geld te verplaatsen."},
            },
        ),
        Action(
            id="crypto_verification", family="protect", moment="fraud", product="vérification humaine",
            value_customer=0.9, value_bank=0.2, sensitivity=0.4, urgency=0.9, is_commercial=False, legal_basis="fraud_prevention",
            sensitive_topic=True,
            ctas=(_cta("book_call", "Être appelé avant l'exécution", "Gebeld worden voor de uitvoering", "advisor_task"),),
            copy={
                "fr": {"title": "Vérifions ensemble ce premier virement crypto",
                       "body": "C'est la première fois que vous envoyez de l'argent vers cette plateforme. Un conseiller vous appelle pour vérifier avec vous avant l'exécution."},
                "nl": {"title": "Laten we deze eerste crypto-overschrijving samen nakijken",
                       "body": "Het is de eerste keer dat u geld naar dit platform stuurt. Een adviseur belt u om het samen na te kijken vóór de uitvoering."},
            },
        ),
        Action(
            id="first_salary_budget", family="inform", moment="first_job", product="éducation financière + épargne auto",
            value_customer=0.8, value_bank=0.2, sensitivity=0.1, urgency=0.55, is_commercial=False,
            ctas=(
                _cta("setup_auto_savings", "Activer l'épargne automatique", "Automatisch sparen activeren", "complete"),
                LEARN,
            ),
            copy={
                "fr": {"title": "Premier salaire : bien démarrer",
                       "body": "Une règle simple pour commencer : 50 % pour l'essentiel, 30 % pour vos envies, 20 % pour l'épargne. Vous pouvez automatiser ces 20 % le jour de votre salaire, et les modifier quand vous voulez."},
                "nl": {"title": "Eerste loon: goed van start",
                       "body": "Een eenvoudige regel om te beginnen: 50 % voor het essentiële, 30 % voor wat u graag doet, 20 % om te sparen. U kunt die 20 % automatisch laten sparen op loondag en het altijd aanpassen."},
            },
        ),
        Action(
            id="student_to_standard", family="simplify", moment="first_job", product="migration offre jeune",
            value_customer=0.6, value_bank=0.3, sensitivity=0.1, urgency=0.4, is_commercial=False,
            ctas=(_cta("migrate_account", "Passer à l'offre adaptée en un clic", "Met één klik overstappen", "complete"),),
            copy={
                "fr": {"title": "Votre compte étudiant peut évoluer",
                       "body": "Vous touchez désormais un salaire. Nous pouvons passer votre compte à l'offre adaptée, sans changer de numéro de compte ni de carte."},
                "nl": {"title": "Uw studentenrekening kan mee evolueren",
                       "body": "U ontvangt nu een loon. We kunnen uw rekening omzetten naar de gepaste formule, zonder nieuw rekeningnummer of nieuwe kaart."},
            },
        ),
        Action(
            id="overdraft_alert", family="protect", moment="financial_stress", product="alerte découvert",
            value_customer=0.85, value_bank=0.1, sensitivity=0.4, urgency=0.8, is_commercial=False,
            ctas=(_cta("shift_payment", "Décaler un paiement", "Een betaling verschuiven", "complete"), BOOK),
            copy={
                "fr": {"title": "Attention : découvert probable dans les prochains jours",
                       "body": "Avec les paiements prévus, votre solde risque de passer sous zéro. Vous pouvez décaler un paiement non urgent dès maintenant."},
                "nl": {"title": "Let op: waarschijnlijk debetstand de komende dagen",
                       "body": "Met de geplande betalingen dreigt uw saldo onder nul te gaan. U kunt nu al een niet-dringende betaling verschuiven."},
            },
        ),
        Action(
            id="job_loss_support", family="accompany", moment="income_loss", product="accompagnement",
            value_customer=0.95, value_bank=0.1, sensitivity=0.7, urgency=0.8, is_commercial=False, sensitive_topic=True,
            ctas=(BOOK,),
            copy={
                "fr": {"title": "Nous sommes là si vous en avez besoin",
                       "body": "Nous n'avons pas vu votre revenu habituel ce mois-ci. Si votre situation change, un conseiller peut revoir vos charges fixes avec vous. Aucune offre de crédit ne vous sera faite."},
                "nl": {"title": "We zijn er als u ons nodig hebt",
                       "body": "We zagen deze maand uw gebruikelijke inkomen niet. Als uw situatie verandert, kan een adviseur samen met u uw vaste kosten bekijken. U krijgt geen kredietaanbod."},
            },
        ),
        Action(
            id="loan_simulation_resume", family="simplify", moment="housing", product="crédit logement",
            value_customer=0.6, value_bank=0.7, sensitivity=0.3, urgency=0.5, is_commercial=True, involves_credit=True,
            ctas=(_cta("resume_simulation", "Reprendre ma simulation", "Mijn simulatie hervatten", "complete"), BOOK),
            copy={
                "fr": {"title": "Votre simulation de prêt vous attend",
                       "body": "Vous avez commencé une simulation de prêt logement. Reprenez là où vous vous êtes arrêté, ou faites-la avec un conseiller. La décision de crédit est toujours prise par une personne."},
                "nl": {"title": "Uw leningsimulatie wacht op u",
                       "body": "U begon een simulatie voor een woonkrediet. Ga verder waar u stopte, of doe het samen met een adviseur. De kredietbeslissing wordt altijd door een mens genomen."},
            },
        ),
        Action(
            id="fixed_rate_end_review", family="inform", moment="product_deadline", product="fin de taux fixe",
            value_customer=0.75, value_bank=0.6, sensitivity=0.2, urgency=0.6, is_commercial=True, involves_credit=True,
            ctas=(_cta("compare_options", "Comparer mes options", "Mijn opties vergelijken", "complete"), BOOK),
            copy={
                "fr": {"title": "Votre taux fixe se termine dans quelques mois",
                       "body": "C'est le bon moment pour comparer vos options avant l'échéance, sans pression."},
                "nl": {"title": "Uw vaste rentevoet loopt binnen enkele maanden af",
                       "body": "Een goed moment om uw opties te vergelijken vóór de vervaldag, zonder druk."},
            },
        ),
        Action(
            id="car_insurance_renewal", family="simplify", moment="product_deadline", product="assurance auto",
            value_customer=0.6, value_bank=0.5, sensitivity=0.1, urgency=0.6, is_commercial=True,
            ctas=(_cta("confirm_renewal", "Confirmer le renouvellement pré-rempli", "Voorbereide verlenging bevestigen", "complete"),),
            copy={
                "fr": {"title": "Assurance auto : renouvellement prêt",
                       "body": "Tout est pré-rempli avec vos informations actuelles. Vérifiez et confirmez en un clic."},
                "nl": {"title": "Autoverzekering: verlenging klaar",
                       "body": "Alles is ingevuld met uw huidige gegevens. Controleer en bevestig met één klik."},
            },
        ),
        Action(
            id="pension_savings_tax", family="inform", moment="calendar", product="épargne-pension",
            value_customer=0.7, value_bank=0.4, sensitivity=0.1, urgency=0.5, is_commercial=True,
            ctas=(_cta("top_up_pension", "Verser le montant restant", "Het resterende bedrag storten", "complete"), LEARN),
            copy={
                "fr": {"title": "Avantage fiscal encore disponible",
                       "body": "Il vous reste une marge d'épargne-pension déductible cette année. Vous pouvez la compléter en un clic avant le 31 décembre."},
                "nl": {"title": "Belastingvoordeel nog beschikbaar",
                       "body": "U hebt dit jaar nog ruimte voor fiscaal aftrekbaar pensioensparen. Vul het aan met één klik vóór 31 december."},
            },
        ),
        Action(
            id="retirement_planning", family="accompany", moment="retirement", product="bilan retraite",
            value_customer=0.8, value_bank=0.4, sensitivity=0.3, urgency=0.4, is_commercial=False,
            ctas=(BOOK,),
            copy={
                "fr": {"title": "Préparer votre retraite sereinement",
                       "body": "Votre crédit se termine bientôt et une nouvelle étape approche. Un bilan retraite avec un conseiller peut vous aider à y voir clair."},
                "nl": {"title": "Uw pensioen rustig voorbereiden",
                       "body": "Uw krediet loopt binnenkort af en een nieuwe levensfase komt eraan. Een pensioenbalans met een adviseur helpt u helder te kijken."},
            },
        ),
    ]
}

# Phrase d'accroche selon la variante "warm" (testée par le bandit contre "direct")
WARM_INTRO = {
    "fr": {
        "baby": "Félicitations pour cette belle nouvelle ! ",
        "grandchild": "Quelle belle nouvelle dans votre famille ! ",
        "first_job": "Bravo pour ce premier salaire ! ",
        "fraud": "Nous préférons vérifier avec vous. ",
        "financial_stress": "Nous gardons un œil sur votre compte pour vous. ",
        "income_loss": "",
        "housing": "Un projet de logement, c'est une grande étape. ",
        "product_deadline": "",
        "calendar": "",
        "retirement": "",
    },
    "nl": {
        "baby": "Proficiat met dit mooie nieuws! ",
        "grandchild": "Wat een mooi nieuws in uw familie! ",
        "first_job": "Proficiat met uw eerste loon! ",
        "fraud": "We kijken dit liever samen met u na. ",
        "financial_stress": "We houden uw rekening voor u in de gaten. ",
        "income_loss": "",
        "housing": "Een woonproject is een grote stap. ",
        "product_deadline": "",
        "calendar": "",
        "retirement": "",
    },
}

ABSTAIN_COPY = {
    "fr": {"title": "Aucune proposition aujourd'hui",
           "body": "Nous n'avons rien d'utile à vous proposer en ce moment, alors nous préférons ne pas vous déranger."},
    "nl": {"title": "Vandaag geen voorstel",
           "body": "We hebben op dit moment niets nuttigs voor u, dus we storen u liever niet."},
}


def get_action(action_id: str) -> Action | None:
    """Validation côté serveur : une action inconnue n'existe tout simplement pas."""
    return CATALOG.get(action_id)


def cta_for(action_id: str, cta_id: str) -> Cta | None:
    action = get_action(action_id)
    if not action:
        return None
    return next((c for c in action.ctas if c.id == cta_id), None)
