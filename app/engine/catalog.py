"""Action catalogue: the ONLY list of actions the engine (and therefore the customer) can trigger.

Any action_id or cta_id received from outside is validated against this catalogue on the server.
Copy is written in English, French and Dutch.
"""
from __future__ import annotations

from dataclasses import dataclass

# The 6 action families
FAMILIES = ("inform", "protect", "simplify", "propose", "accompany", "abstain")

# What the server does when the customer presses a button
CTA_EFFECTS = ("complete", "ack", "book", "callback", "fraud_call", "cancel_transfer", "confirm_transfer")


@dataclass(frozen=True)
class Cta:
    id: str
    label: dict[str, str]           # {"en": ..., "fr": ..., "nl": ...}
    effect: str


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
    copy: dict[str, dict[str, str]]  # language -> {title, body, push}
    legal_basis: str = "consent"     # consent | fraud_prevention
    sensitive_topic: bool = False    # stress, income loss, complex fraud -> a human
    involves_credit: bool = False    # GDPR art. 22: never an automated decision
    variants: tuple[str, ...] = ("warm", "direct")

    @property
    def bookable(self) -> bool:
        return any(c.effect == "book" for c in self.ctas)


def _cta(id_: str, en: str, fr: str, nl: str, effect: str) -> Cta:
    assert effect in CTA_EFFECTS
    return Cta(id=id_, label={"en": en, "fr": fr, "nl": nl}, effect=effect)


def _copy(en: tuple[str, str, str], fr: tuple[str, str, str], nl: tuple[str, str, str]) -> dict[str, dict[str, str]]:
    """(title, body, short push text) for each language."""
    return {lang: {"title": t, "body": b, "push": p} for lang, (t, b, p) in (("en", en), ("fr", fr), ("nl", nl))}


BOOK = _cta("book_appointment", "Book a time with an advisor", "Prendre rendez-vous avec un conseiller",
            "Afspraak maken met een adviseur", "book")
LEARN = _cta("learn_more", "Learn more", "En savoir plus", "Meer weten", "ack")

CATALOG: dict[str, Action] = {
    a.id: a
    for a in [
        Action(
            id="family_insurance_review", family="propose", moment="baby", product="family insurance + child savings",
            value_customer=0.8, value_bank=0.5, sensitivity=0.3, urgency=0.6, is_commercial=True,
            ctas=(
                _cta("start_review", "Review my cover (2 min)", "Revoir ma couverture (2 min)", "Mijn dekking nakijken (2 min)", "complete"),
                _cta("open_child_savings", "Open a child savings account", "Ouvrir une épargne enfant", "Kinderspaarrekening openen", "complete"),
                BOOK,
            ),
            copy=_copy(
                ("A new family member?", "Does your family insurance already cover your child? Check in two minutes, and see how to start saving for them today.", "Is your little one already covered? Check in 2 minutes."),
                ("Un nouveau membre dans la famille ?", "Votre assurance familiale couvre-t-elle déjà votre enfant ? Vérifiez en deux minutes, et découvrez comment commencer une épargne pour lui dès aujourd'hui.", "Votre enfant est-il déjà couvert ? Vérifiez en 2 minutes."),
                ("Een nieuw gezinslid?", "Is uw kind al gedekt door uw gezinsverzekering? Controleer het in twee minuten en ontdek hoe u vandaag al voor hem of haar kunt sparen.", "Is uw kind al gedekt? Controleer het in 2 minuten."),
            ),
        ),
        Action(
            id="family_budget_support", family="accompany", moment="baby", product="budget support",
            value_customer=0.95, value_bank=0.1, sensitivity=0.6, urgency=0.85, is_commercial=False, sensitive_topic=True,
            ctas=(
                BOOK,
                _cta("open_budget_plan", "See my budget plan", "Voir mon budget prévisionnel", "Mijn budgetplanning bekijken", "complete"),
            ),
            copy=_copy(
                ("A budget that follows your new life", "A new child changes a lot. We prepared a budget plan for the coming months, and an advisor can go through it with you, with no obligation and no sales offer.", "A budget plan for the months ahead, if you want it."),
                ("Un budget qui suit votre nouvelle vie", "L'arrivée d'un enfant change beaucoup de choses. Nous avons préparé un budget prévisionnel pour les prochains mois, et un conseiller peut le revoir avec vous, sans engagement et sans aucune offre commerciale.", "Un budget prévisionnel pour les prochains mois, si vous le souhaitez."),
                ("Een budget dat met uw nieuwe leven meegaat", "De komst van een kind verandert veel. We hebben een budgetplanning voor de komende maanden voorbereid en een adviseur kan die vrijblijvend met u overlopen, zonder commercieel aanbod.", "Een budgetplanning voor de komende maanden, als u dat wilt."),
            ),
        ),
        Action(
            id="grandchild_savings_info", family="inform", moment="grandchild", product="gift / grandchild savings",
            value_customer=0.7, value_bank=0.3, sensitivity=0.3, urgency=0.35, is_commercial=False,
            ctas=(
                _cta("callback_request", "Have an advisor call me back", "Être rappelé par un conseiller", "Teruggebeld worden door een adviseur", "callback"),
                LEARN,
            ),
            copy=_copy(
                ("Helping a grandchild, with peace of mind", "You are supporting a young parent in your family. There are simple ways to save for a grandchild, and a bank gift has tax rules worth knowing. An advisor can explain them.", "Saving for a grandchild: a few things worth knowing."),
                ("Aider un petit-enfant, en toute sérénité", "Vous soutenez un jeune parent de votre famille. Il existe des façons simples d'épargner pour un petit-enfant, et la donation bancaire a des règles fiscales à connaître. Un conseiller peut vous les expliquer.", "Épargner pour un petit-enfant : ce qu'il faut savoir."),
                ("Een kleinkind helpen, met een gerust gevoel", "U steunt een jonge ouder in uw familie. Er zijn eenvoudige manieren om voor een kleinkind te sparen, en een bankschenking heeft fiscale regels die u best kent. Een adviseur legt het u graag uit.", "Sparen voor een kleinkind: goed om te weten."),
            ),
        ),
        Action(
            id="scam_pause", family="protect", moment="fraud", product="scam protection",
            value_customer=1.0, value_bank=0.2, sensitivity=0.2, urgency=1.0, is_commercial=False, legal_basis="fraud_prevention",
            ctas=(
                _cta("cancel_transfer", "Cancel this transfer", "Annuler ce virement", "Deze overschrijving annuleren", "cancel_transfer"),
                _cta("confirm_transfer", "I know this beneficiary, confirm", "Je connais ce bénéficiaire, confirmer", "Ik ken deze begunstigde, bevestigen", "confirm_transfer"),
                _cta("call_bank", "Talk to someone now", "Parler à quelqu'un maintenant", "Nu met iemand praten", "fraud_call"),
            ),
            copy=_copy(
                ("10-minute safety pause", "This transfer goes to a beneficiary you have never paid, for an unusual amount. Scammers often pretend to be the bank or a technical service and rush their victims. Take 10 minutes: nobody from the bank will ever ask you to move your money.", "We paused an unusual transfer for 10 minutes. Please check."),
                ("Pause de sécurité de 10 minutes", "Ce virement va vers un bénéficiaire que vous n'avez jamais payé, pour un montant inhabituel. Les arnaqueurs se font souvent passer pour la banque ou un service technique et pressent leurs victimes. Prenez 10 minutes : personne de la banque ne vous demandera jamais de déplacer votre argent.", "Nous avons mis en pause un virement inhabituel. Vérifiez-le."),
                ("Veiligheidspauze van 10 minuten", "Deze overschrijving gaat naar een begunstigde die u nog nooit betaalde, voor een ongewoon bedrag. Oplichters doen zich vaak voor als de bank of een technische dienst en zetten hun slachtoffers onder druk. Neem 10 minuten: niemand van de bank zal u ooit vragen uw geld te verplaatsen.", "We hebben een ongewone overschrijving gepauzeerd. Kijk even na."),
            ),
        ),
        Action(
            id="crypto_verification", family="protect", moment="fraud", product="human verification",
            value_customer=0.9, value_bank=0.2, sensitivity=0.4, urgency=0.9, is_commercial=False, legal_basis="fraud_prevention",
            sensitive_topic=True,
            ctas=(_cta("book_call", "Get a call before execution", "Être appelé avant l'exécution", "Gebeld worden voor de uitvoering", "fraud_call"),),
            copy=_copy(
                ("Let's check this first crypto transfer together", "This is the first time you send money to this platform. An advisor will call you to check it with you before execution.", "First crypto transfer: we'll call you before executing it."),
                ("Vérifions ensemble ce premier virement crypto", "C'est la première fois que vous envoyez de l'argent vers cette plateforme. Un conseiller vous appelle pour vérifier avec vous avant l'exécution.", "Premier virement crypto : nous vous appelons avant l'exécution."),
                ("Laten we deze eerste crypto-overschrijving samen nakijken", "Het is de eerste keer dat u geld naar dit platform stuurt. Een adviseur belt u om het samen na te kijken vóór de uitvoering.", "Eerste crypto-overschrijving: we bellen u vóór de uitvoering."),
            ),
        ),
        Action(
            id="first_salary_budget", family="inform", moment="first_job", product="money basics + auto-savings",
            value_customer=0.8, value_bank=0.2, sensitivity=0.1, urgency=0.55, is_commercial=False,
            ctas=(
                _cta("setup_auto_savings", "Turn on automatic savings", "Activer l'épargne automatique", "Automatisch sparen activeren", "complete"),
                LEARN,
            ),
            copy=_copy(
                ("First salary: a good start", "A simple rule to begin with: 50% for essentials, 30% for things you enjoy, 20% for savings. You can move that 20% automatically on payday, and change it whenever you like.", "First salary in! A simple rule to get started."),
                ("Premier salaire : bien démarrer", "Une règle simple pour commencer : 50 % pour l'essentiel, 30 % pour vos envies, 20 % pour l'épargne. Vous pouvez automatiser ces 20 % le jour de votre salaire, et les modifier quand vous voulez.", "Premier salaire reçu ! Une règle simple pour bien démarrer."),
                ("Eerste loon: goed van start", "Een eenvoudige regel om te beginnen: 50% voor het essentiële, 30% voor wat u graag doet, 20% om te sparen. U kunt die 20% automatisch laten sparen op loondag en het altijd aanpassen.", "Eerste loon binnen! Een eenvoudige regel om te starten."),
            ),
        ),
        Action(
            id="student_to_standard", family="simplify", moment="first_job", product="youth offer migration",
            value_customer=0.6, value_bank=0.3, sensitivity=0.1, urgency=0.4, is_commercial=False,
            ctas=(_cta("migrate_account", "Switch to the right offer in one tap", "Passer à l'offre adaptée en un clic", "Met één klik overstappen", "complete"),),
            copy=_copy(
                ("Your student account can grow with you", "You now receive a salary. We can switch your account to the right offer, without changing your account number or card.", "Your account can switch to the right offer in one tap."),
                ("Votre compte étudiant peut évoluer", "Vous touchez désormais un salaire. Nous pouvons passer votre compte à l'offre adaptée, sans changer de numéro de compte ni de carte.", "Votre compte peut passer à l'offre adaptée en un clic."),
                ("Uw studentenrekening kan mee evolueren", "U ontvangt nu een loon. We kunnen uw rekening omzetten naar de gepaste formule, zonder nieuw rekeningnummer of nieuwe kaart.", "Uw rekening kan met één klik overstappen."),
            ),
        ),
        Action(
            id="overdraft_alert", family="protect", moment="financial_stress", product="overdraft alert",
            value_customer=0.85, value_bank=0.1, sensitivity=0.4, urgency=0.8, is_commercial=False,
            ctas=(_cta("shift_payment", "Move a payment", "Décaler un paiement", "Een betaling verschuiven", "complete"), BOOK),
            copy=_copy(
                ("Heads up: likely overdraft in the next few days", "With the payments scheduled this week, your balance may go below zero. You can move a non-urgent payment right now.", "Your balance may go below zero this week. Tap to act."),
                ("Attention : découvert probable dans les prochains jours", "Avec les paiements prévus cette semaine, votre solde risque de passer sous zéro. Vous pouvez décaler un paiement non urgent dès maintenant.", "Votre solde risque de passer sous zéro cette semaine."),
                ("Let op: waarschijnlijk debetstand de komende dagen", "Met de geplande betalingen deze week dreigt uw saldo onder nul te gaan. U kunt nu al een niet-dringende betaling verschuiven.", "Uw saldo dreigt deze week onder nul te gaan."),
            ),
        ),
        Action(
            id="job_loss_support", family="accompany", moment="income_loss", product="support",
            value_customer=0.95, value_bank=0.1, sensitivity=0.7, urgency=0.8, is_commercial=False, sensitive_topic=True,
            ctas=(BOOK,),
            copy=_copy(
                ("We are here if you need us", "We did not see your usual income this month. If your situation changes, an advisor can review your fixed costs with you. You will not get any credit offer.", "We are here if you need us."),
                ("Nous sommes là si vous en avez besoin", "Nous n'avons pas vu votre revenu habituel ce mois-ci. Si votre situation change, un conseiller peut revoir vos charges fixes avec vous. Aucune offre de crédit ne vous sera faite.", "Nous sommes là si vous en avez besoin."),
                ("We zijn er als u ons nodig hebt", "We zagen deze maand uw gebruikelijke inkomen niet. Als uw situatie verandert, kan een adviseur samen met u uw vaste kosten bekijken. U krijgt geen kredietaanbod.", "We zijn er als u ons nodig hebt."),
            ),
        ),
        Action(
            id="loan_simulation_resume", family="simplify", moment="housing", product="home loan",
            value_customer=0.6, value_bank=0.7, sensitivity=0.3, urgency=0.5, is_commercial=True, involves_credit=True,
            ctas=(_cta("resume_simulation", "Resume my simulation", "Reprendre ma simulation", "Mijn simulatie hervatten", "complete"), BOOK),
            copy=_copy(
                ("Your loan simulation is waiting for you", "You started a home loan simulation. Pick up where you left off, or do it with an advisor. The credit decision is always made by a person.", "Your home loan simulation is saved. Pick up where you left off."),
                ("Votre simulation de prêt vous attend", "Vous avez commencé une simulation de prêt logement. Reprenez là où vous vous êtes arrêté, ou faites-la avec un conseiller. La décision de crédit est toujours prise par une personne.", "Votre simulation de prêt est sauvegardée."),
                ("Uw leningsimulatie wacht op u", "U begon een simulatie voor een woonkrediet. Ga verder waar u stopte, of doe het samen met een adviseur. De kredietbeslissing wordt altijd door een mens genomen.", "Uw leningsimulatie is bewaard."),
            ),
        ),
        Action(
            id="fixed_rate_end_review", family="inform", moment="product_deadline", product="fixed rate ending",
            value_customer=0.75, value_bank=0.6, sensitivity=0.2, urgency=0.6, is_commercial=True, involves_credit=True,
            ctas=(_cta("compare_options", "Compare my options", "Comparer mes options", "Mijn opties vergelijken", "complete"), BOOK),
            copy=_copy(
                ("Your fixed rate ends in a few months", "A good moment to compare your options before the deadline, without pressure.", "Your fixed rate ends soon: compare your options."),
                ("Votre taux fixe se termine dans quelques mois", "C'est le bon moment pour comparer vos options avant l'échéance, sans pression.", "Votre taux fixe se termine bientôt."),
                ("Uw vaste rentevoet loopt binnen enkele maanden af", "Een goed moment om uw opties te vergelijken vóór de vervaldag, zonder druk.", "Uw vaste rentevoet loopt binnenkort af."),
            ),
        ),
        Action(
            id="car_insurance_renewal", family="simplify", moment="product_deadline", product="car insurance",
            value_customer=0.6, value_bank=0.5, sensitivity=0.1, urgency=0.6, is_commercial=True,
            ctas=(_cta("confirm_renewal", "Confirm the pre-filled renewal", "Confirmer le renouvellement pré-rempli", "Voorbereide verlenging bevestigen", "complete"),),
            copy=_copy(
                ("Car insurance: renewal ready", "Everything is pre-filled with your current details. Check and confirm in one tap.", "Your car insurance renewal is ready."),
                ("Assurance auto : renouvellement prêt", "Tout est pré-rempli avec vos informations actuelles. Vérifiez et confirmez en un clic.", "Votre renouvellement d'assurance auto est prêt."),
                ("Autoverzekering: verlenging klaar", "Alles is ingevuld met uw huidige gegevens. Controleer en bevestig met één klik.", "Uw verlenging van de autoverzekering is klaar."),
            ),
        ),
        Action(
            id="pension_savings_tax", family="inform", moment="calendar", product="pension savings",
            value_customer=0.7, value_bank=0.4, sensitivity=0.1, urgency=0.5, is_commercial=True,
            ctas=(_cta("top_up_pension", "Pay in the remaining amount", "Verser le montant restant", "Het resterende bedrag storten", "complete"), LEARN),
            copy=_copy(
                ("Tax benefit still available", "You still have room for tax-deductible pension savings this year. Top it up in one tap before 31 December.", "Tax benefit still available this year."),
                ("Avantage fiscal encore disponible", "Il vous reste une marge d'épargne-pension déductible cette année. Vous pouvez la compléter en un clic avant le 31 décembre.", "Avantage fiscal encore disponible cette année."),
                ("Belastingvoordeel nog beschikbaar", "U hebt dit jaar nog ruimte voor fiscaal aftrekbaar pensioensparen. Vul het aan met één klik vóór 31 december.", "Belastingvoordeel nog beschikbaar dit jaar."),
            ),
        ),
        Action(
            id="retirement_planning", family="accompany", moment="retirement", product="retirement review",
            value_customer=0.8, value_bank=0.4, sensitivity=0.3, urgency=0.4, is_commercial=False,
            ctas=(BOOK,),
            copy=_copy(
                ("Preparing your retirement calmly", "Your loan ends soon and a new stage is coming. A retirement review with an advisor can help you see clearly.", "A retirement review, when you are ready."),
                ("Préparer votre retraite sereinement", "Votre crédit se termine bientôt et une nouvelle étape approche. Un bilan retraite avec un conseiller peut vous aider à y voir clair.", "Un bilan retraite, quand vous voulez."),
                ("Uw pensioen rustig voorbereiden", "Uw krediet loopt binnenkort af en een nieuwe levensfase komt eraan. Een pensioenbalans met een adviseur helpt u helder te kijken.", "Een pensioenbalans, wanneer u wilt."),
            ),
        ),
    ]
}


def get_action(action_id: str) -> Action | None:
    """Server-side validation: an unknown action simply does not exist."""
    return CATALOG.get(action_id)


def cta_for(action_id: str, cta_id: str) -> Cta | None:
    action = get_action(action_id)
    if not action:
        return None
    return next((c for c in action.ctas if c.id == cta_id), None)
