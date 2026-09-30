# Vision

> Le brief demande d'abord d'imaginer l'expérience idéale **sans contraintes**, puis de montrer comment la livrer à **plus de 2,3 millions de clients**. Ce document fait les deux.

## Une phrase

La banque détecte le *moment* dans lequel se trouve chaque client, décide **une seule** bonne action au bon moment, l'affiche sur le bon canal, et explique toujours pourquoi. Quand rien n'est utile, elle ne dit rien.

## L'expérience idéale, sans contraintes

**Sarah, 33 ans, Gand. Une année avec sa banque en 2030.**

- **Mars.** Sarah achète une poussette et commence, un soir, une simulation d'assurance familiale qu'elle ne termine pas. Le lendemain matin, son app ne lui propose pas « nos offres du mois ». Elle lui pose une seule question : *« Un nouveau membre dans la famille ? Votre couverture inclut-elle déjà votre enfant ? »* Deux minutes, c'est réglé. Sous le message, un lien *« Pourquoi je vois ça ? »* lui montre exactement ce que la banque a remarqué, et un bouton pour couper ces données.
- **Juin.** Congé de maternité, revenus en baisse. La banque le voit aussi. Cette fois, **aucune offre** : un budget prévisionnel des six prochains mois, et une conseillère qui propose un appel sans rien vendre. Sarah n'a jamais eu à expliquer sa situation.
- **Septembre.** Sa mère Monique, 67 ans, qui n'ouvre presque jamais l'app, reçoit un court message vocal dans sa langue. Il lui explique comment épargner pour sa petite-fille et ce qu'il faut savoir sur la donation, puis lui propose d'être rappelée.
- **Novembre.** Le voisin de Monique, Marcel, reçoit un appel d'un « service technique de la banque » qui lui demande de « sécuriser » 4 900 €. Au moment du virement, sa banque l'arrête doucement : *« Pause de 10 minutes. Personne de la banque ne vous demandera jamais de déplacer votre argent. »* Il annule.
- **Le reste de l'année.** La plupart des jours, la banque ne dit rien. C'est voulu.

Ce que Sarah retient, ce n'est pas un produit. C'est que sa banque **comprend sa situation, agit au bon moment, sait se taire, et ne profite jamais d'un moment difficile**.

## Les principes qui en découlent

1. **Une décision par client et par moment**, pas une campagne par segment.
2. **Le même signal peut mener à des décisions opposées.** L'arrivée d'un bébé déclenche une proposition chez Emma et un accompagnement sans vente chez Sofia.
3. **S'abstenir est une action à part entière**, visible et expliquée.
4. **La valeur client pèse plus que la valeur banque** dans le score (0,35 contre 0,10).
5. **La transparence est un réflexe** : chaque message a son « pourquoi », construit par le moteur, pas par une IA générative.
6. **Le client garde la main** : il coupe une famille de données, et elle n'est plus calculée du tout.
7. **Les humains restent dans la boucle** pour les sujets sensibles et pour toute décision de crédit.
8. **L'IA générative met en forme, elle ne décide jamais.** C'est ce qui rend l'ensemble auditable, conforme et abordable à l'échelle.

## Les six familles d'actions

| Famille | Idée | Exemple de la démo |
| --- | --- | --- |
| Informer | Une info utile, sans rien vendre | Yasmine : règle 50/30/20 |
| Protéger | Éviter un problème | Marcel : pause anti-arnaque |
| Simplifier | Faire à la place du client, ou en un clic | Nina : reprendre la simulation |
| Proposer | Un produit adapté au moment | Emma : assurance famille |
| Accompagner | Mettre un humain dans la boucle | Sofia : budget + conseiller |
| **S'abstenir** | Ne rien faire, et le dire | Thomas |

Catalogue complet par moment de vie : voir `app/engine/catalog.py` et [DECISION_ENGINE.md](DECISION_ENGINE.md).

## Réponses aux 5 questions du brief

**1. Quels signaux aident à comprendre les besoins ?**
Quatre familles, chacune soumise au consentement : transactions (salaire, catégories de dépenses, solde, épargne, frais de retard), usage digital (simulations commencées ou abandonnées, pages consultées), produits et échéances (fin de taux fixe, renouvellements), profil (âge, ménage, langue). La prévention de la fraude a sa propre base légale. Les données de santé, de convictions ou d'orientation sont **exclues avant tout calcul**. Détails : [PRIVACY.md](PRIVACY.md).

**2. Comment reconnaître les clients selon leur situation, leur comportement et leur intention ?**
Par des **signaux dérivés** avec une confiance de 0 à 1 et des preuves lisibles : `life_event` (bébé, petit-enfant, premier emploi, logement, perte de revenu, retraite), `financial_stress` (niveau 0 à 3), `intent`, `scam_risk`, échéances, préférence de canal. Le moteur n'agit qu'au-dessus d'une confiance de 0,6.

**3. Comment les expériences s'adaptent-elles automatiquement à chaque client ?**
Le moteur choisit l'action (score + garde-fous), le canal (app, notification, voix, humain) et le ton (appris par un bandit). Le rendu adapte la langue et la formulation. L'écran est assemblé à partir de blocs connus, donc deux clients ouvrent la même app et voient des écrans différents.

**4. Comment cela fonctionne-t-il à travers produits, services et canaux ?**
Un seul catalogue d'actions couvre banque, assurance et services, ce qui est l'avantage d'une bancassurance : un moment de vie touche les deux à la fois. Le canal est une *décision*, pas un silo : même moteur, même journal, que le message arrive dans l'app, par la voix ou par un conseiller.

**5. Comment avoir un impact pour des millions de clients en même temps ?**
La détection et la décision sont **déterministes** : ≈ 33 000 clients par seconde sur un cœur, soit 2,3 M en environ une minute. L'IA générative n'intervient que pour les clients qui déclenchent une action, et le texte est **mis en cache par segment × moment × langue × ton** : quelques milliers de textes pour toute la base. Voir [SCALABILITY.md](SCALABILITY.md).
