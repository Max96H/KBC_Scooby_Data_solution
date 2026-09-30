# La boucle d'apprentissage

Code : `app/engine/feedback.py`, simulation : `scripts/simulate_feedback.py`, visualisation : espace conseiller.

```
Action envoyée → Réaction du client → Efficacité de l'action (par segment) → Ajustement du score → Meilleur envoi
```

## Ce qu'on enregistre (`action_events`)

Une ligne par décision envoyée : identifiant client **pseudonymisé**, action, segment (tranche d'âge × ménage), canal, variante de ton, date d'envoi, réaction, date de réaction, ouverture du panneau « pourquoi ». Aucune donnée transactionnelle.

## Réactions et poids

| Réaction | Poids | Qui la pose |
| --- | --- | --- |
| Ignoré | 0 | serveur (par défaut) |
| Vu | +0,1 | serveur, à l'affichage |
| Clic / « Utile » | +0,3 | client |
| **Action utile complétée** (révision faite, RDV pris, virement annulé…) | **+1,0** | **serveur uniquement**, quand le bouton est exécuté |
| « Pas maintenant » | −0,5 | client → pause de 30 jours |
| « Ne plus voir ça » | −1,0 | client → suppression définitive |
| Signalé comme intrusif | −1,5 | client → suppression définitive |

Règles : on garde la réaction la plus forte, et **un refus ne peut jamais être effacé** par une réaction positive. Le client ne peut pas se déclarer « complété » lui-même (test : `test_client_cannot_self_report_completed`).

## Efficacité

```
efficacité(action, segment) = moyenne des poids sur 30 jours, ramenée sur [0, 1]
score_final = score_base × (0,7 + 0,3 × efficacité)
```

L'influence est bornée à 30 % : l'apprentissage ne peut pas faire passer une action devant un garde-fou, et une action bloquée reste bloquée quel que soit son score.

## Explorer ou exploiter : bandit de Thompson

Pour chaque action × segment, chaque variante de ton (`warm`, `direct`) a une loi Beta(1 + succès, 1 + échecs). À chaque nouvelle décision, on tire dans chaque loi et on garde le meilleur tirage. Les bonnes variantes prennent naturellement plus de trafic, et les autres continuent d'être testées tant qu'il y a de l'incertitude.

Dans la simulation, l'effet caché est : ton chaleureux meilleur pour les moments heureux (bébé, petit-enfant), ton direct meilleur pour la protection (arnaque, découvert). L'espace conseiller montre le bandit qui le découvre. Test : `test_thompson_prefers_better_variant`.

**Ce qu'on optimise :** le ton (et, en production : la formulation, le canal, l'heure). **Ce qu'on n'optimise jamais :** le fait d'envoyer une offre à un client en stress financier, ou d'outrepasser un refus.

## Garde-fous de l'apprentissage

1. **On optimise la valeur, pas le clic** : +1,0 pour une action utile complétée, +0,3 pour un clic.
2. **Les règles éthiques priment sur les scores.**
3. **Un refus est une information, pas un obstacle à contourner** : la fréquence baisse, elle ne monte jamais.
4. **Équité** : l'espace conseiller compare la part d'actions commerciales et le taux de refus par tranche d'âge, et lève une alerte quand une tranche reçoit plus de 1,5 fois la pression commerciale moyenne. Dans la simulation, l'alerte se déclenche pour les 26-44 et 45-64 ans : c'est exactement ce que ce tableau doit rendre visible.
5. **Données minimales** : réaction + pseudonyme, rien d'autre.

## Honnêtement

Le feedback de la démo est **simulé** : 400 clients synthétiques sur 30 jours, avec des probabilités de réaction fixées dans `scripts/simulate_feedback.py`. Il n'y a pas d'apprentissage en production.
