# Le moteur de décision

Code : `app/engine/signals.py`, `app/engine/decision.py`, `app/engine/catalog.py`.

## 1. Signaux dérivés

Chaque signal porte une **valeur**, une **confiance** de 0 à 1, les **familles de données** utilisées (pour le consentement) et des **preuves** lisibles (codes traduits en FR/NL pour le panneau « pourquoi »).

| Signal | Règle (simplifiée) | Confiance |
| --- | --- | --- |
| `life_event = baby` | achats en magasin bébé (60 j) +0,45, ≥ 3 achats +0,10 ; simulation « assurance famille » +0,35 ; ménage de 22 à 45 ans +0,10 | max 0,95 |
| `life_event = grandchild` | virement « naissance » +0,50 ; virement familial mensuel sur 3 mois +0,25 ; 55 ans et plus +0,15 | |
| `life_event = first_job` | premier salaire du semestre 0,65 ; compte étudiant +0,15 ; 27 ans ou moins +0,10 | |
| `life_event = income_loss` | salaire présent ≥ 4 mois sur 5, absent depuis plus de 38 jours | 0,70 |
| `life_event = housing` | frais de notaire ou de déménagement +0,50 ; simulation de prêt abandonnée +0,35 ; ≥ 3 visites de pages crédit +0,20 | |
| `life_event = retirement` | 60 à 66 ans et crédit se terminant dans l'année | 0,70 |
| `financial_stress` (0 à 3) | +1 solde en baisse 3 mois de suite ; +1 épargne en baisse ; +1 au moins 2 frais de retard en 90 j ; +1 découvert prévu (si déjà ≥ 1) | 0,6 + 0,1 × niveau |
| `overdraft_risk` | solde − débits récurrents attendus dans 7 j < 0 | 0,80 |
| `intent = mortgage` | simulation de prêt abandonnée, +0,3 si ≥ 3 visites | 0,5 à 0,8 |
| `scam_risk` | bénéficiaire nouveau 0,35 ; ≥ 2 000 € +0,30 ; 65 ans et plus +0,20 ; plateforme crypto +0,25 | base légale : prévention fraude |
| `deadline` | fin de taux fixe ≤ 120 j ; assurance auto ≤ 30 j | 0,90 |
| `calendar = pension_tax` | épargne-pension avec marge restante, octobre à décembre | 0,65 |
| `channel_pref` | peu digital et inactif → voix ; actif ou très digital → app ; sinon push | |

## 2. Des signaux aux actions candidates

| Signal | Actions candidates |
| --- | --- |
| bébé | `family_insurance_review` (Proposer), `family_budget_support` (Accompagner, **seulement si stress ≥ 1**) |
| petit-enfant | `grandchild_savings_info` (Informer) |
| premier emploi | `first_salary_budget` (Informer), `student_to_standard` (Simplifier, si compte étudiant) |
| perte de revenu | `job_loss_support` (Accompagner, aucune offre de crédit) |
| logement / intention | `loan_simulation_resume` (Simplifier, crédit : humain obligatoire) |
| retraite | `retirement_planning` (Accompagner) |
| découvert probable | `overdraft_alert` (Protéger) |
| arnaque | `scam_pause` ou `crypto_verification` (Protéger) |
| échéances | `fixed_rate_end_review`, `car_insurance_renewal` |
| calendrier | `pension_savings_tax` |

Si plusieurs signaux mènent à la même action, on garde le plus sûr.

## 3. Le score

```
score_base  = 0,35·valeur_client + 0,25·urgence + 0,20·confiance + 0,10·valeur_banque − 0,10·sensibilité
score_final = score_base × (0,7 + 0,3 × efficacité)        efficacité ∈ [0, 1], 0,5 sans historique
```

**Choix éthique :** la valeur client pèse 3,5 fois plus que la valeur banque. L'apprentissage (efficacité) ne pèse jamais plus de 30 %.

Les attributs de chaque action (valeur client, valeur banque, urgence, sensibilité, commerciale ou non, base légale, sujet sensible, crédit) sont dans `catalog.py`.

## 4. Les garde-fous (dans l'ordre)

| # | Règle | Effet | Code |
| --- | --- | --- | --- |
| 1 | **Consentement** : une famille de données coupée n'est pas calculée ; une candidate qui en dépendrait est écartée | bloque | `consent_withdrawn` |
| 2 | **Confiance ≥ 0,6** pour agir | bloque | `low_confidence` |
| 3 | **Stress financier ≥ 2 → aucune vente** | bloque les actions commerciales | `financial_stress_no_sales` |
| 4 | **Refus respecté** : pause de 30 jours après « pas maintenant », définitive après « ne plus voir ça » | bloque | `suppressed_after_refusal` |
| 5 | **Stress ≥ 2 → l'aide passe en priorité** (sauf protection anti-fraude) | arbitrage | `stress_prioritizes_help` |
| 6 | **Une seule action à la fois** | arbitrage | `one_action_at_a_time` |
| 7 | **Maximum 1 message proactif (push, voix) par 7 jours** | le canal redescend vers l'app | `frequency_cap` |
| 8 | **Heures calmes 21 h à 8 h** : pas de notification ni d'appel, sauf protection anti-fraude | le canal redescend vers l'app | `quiet_hours` |
| 9 | **Crédit : jamais de décision automatique** (RGPD art. 22) | l'action ne peut que reprendre une simulation ou proposer un rendez-vous | `credit_human_in_the_loop` |

Si aucune candidate ne survit, le moteur **s'abstient** avec une raison explicite (`no_signal`, `low_confidence`, `stress_no_sales`, `all_blocked`), affichée au client.

## 5. Le choix du canal

| Situation | Canal |
| --- | --- |
| Sujet sensible (stress, perte de revenu, vérification crypto) | Humain : proposition de rendez-vous + tâche dans la file conseiller |
| Client peu digital et inactif dans l'app | Voix |
| Client actif dans l'app | Bloc sur l'écran d'accueil |
| Urgence ≥ 0,7 et client inactif | Notification push |
| Sinon | Affiché à la prochaine ouverture de l'app |

Puis les garde-fous 7 et 8 peuvent faire redescendre un canal proactif vers l'app.

## 6. Exemples chiffrés (sans historique de feedback, efficacité = 0,5 → × 0,85)

**Emma** : `life_event = baby` avec une confiance de 0,95 (achats bébé, 4 achats, simulation, ménage jeune).

| Candidate | Base | Final | Statut |
| --- | --- | --- | --- |
| `family_insurance_review` | 0,35·0,8 + 0,25·0,6 + 0,20·0,95 + 0,10·0,5 − 0,10·0,3 = **0,640** | 0,544 | **choisie** |

`family_budget_support` n'est même pas candidate (stress = 0). Canal : app (cliente active).

**Sofia** : même signal bébé (confiance 0,65, sans simulation), mais stress = 3.

| Candidate | Base | Final | Statut |
| --- | --- | --- | --- |
| `family_budget_support` | 0,35·0,95 + 0,25·0,85 + 0,20·0,65 + 0,10·0,1 − 0,10·0,6 = **0,625** | 0,531 | **choisie** |
| `family_insurance_review` | 0,580 | 0,493 | **bloquée** : stress ≥ 2, pas de vente |

Canal : humain (sujet sensible), et une tâche est créée dans la file conseiller.

**Marcel** : `scam_risk = transfer` (0,85). `scam_pause` : base 0,770. Choisie, canal voix (peu digital). Le virement passe en statut `held` pour 10 minutes ; la confirmation avant la fin est refusée par le serveur (HTTP 409).

**Thomas** : aucun signal. **Abstention** (`no_signal`), affichée : « Aucune proposition aujourd'hui ».

## 7. Le journal

Chaque décision produit un journal (stocké avec la décision) : consentements, transactions exclues, signaux, candidates avec leurs scores et raisons, garde-fous, décision, canal et raison, source du rendu, tirages du bandit. Il alimente le panneau « pourquoi » (côté client, version lisible), les coulisses (démo) et l'audit (conseiller).
