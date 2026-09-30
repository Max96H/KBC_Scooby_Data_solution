# Benchmark de passage à l'échelle

Généré par `python -m scripts.benchmark_scale --n 200000` sur x86_64, Python 3.11.15, **un seul cœur**.

| Mesure | Valeur |
| --- | --- |
| Clients synthétiques évalués | 200 000 |
| Temps signaux + décision + garde-fous | 6.00 s |
| Débit | 33 326 clients / s |
| Extrapolation 2,3 M clients (1 cœur) | 69 s ≈ 1.2 min |
| Extrapolation 2,3 M clients (16 cœurs) | ≈ 4 s |
| Clients avec une action | 9.9% |
| Abstentions | 90.1% |

## Répartition des décisions

| Famille | Part |
| --- | --- |
| abstain | 90.07% |
| inform | 4.19% |
| simplify | 2.97% |
| protect | 2.29% |
| accompany | 0.45% |
| propose | 0.02% |

| Canal (clients avec action) | Part |
| --- | --- |
| app | 64.9% |
| voice | 27.0% |
| human | 5.0% |
| push | 3.2% |

## Garde-fous déclenchés

| Garde-fou | Clients concernés |
| --- | --- |
| `abstain` | 90.07% |
| `financial_stress_no_sales` | 1.17% |
| `low_confidence` | 0.81% |
| `credit_human_in_the_loop` | 0.73% |
| `one_action_at_a_time` | 0.46% |
| `stress_prioritizes_help` | 0.07% |

## Lecture

- La décision est déterministe et coûte quelques microsecondes par client : elle peut tourner chaque nuit (ou en streaming) sur 100 % de la base.
- Le LLM n'intervient que pour les clients avec une action, et le texte est réutilisé par segment × moment × langue × ton (voir le calculateur dans l'espace conseiller).
- Les distributions dépendent entièrement du générateur synthétique : elles illustrent la mécanique, pas des taux réels de KBC.
