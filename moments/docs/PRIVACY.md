# Vie privée et conformité

> Analyse de conception pour un PoC, pas un avis juridique. Les bases légales sont à valider avec le DPO.

## Principes appliqués dans le code

| Principe | Implémentation |
| --- | --- |
| **Catégories particulières exclues (RGPD art. 9)** | `engine/sensitive.py` retire santé (pharmacie, médecin, hôpital, santé mentale), convictions (dons religieux, lieux de culte), opinions politiques, syndicats et orientation **avant** tout calcul. Seul leur nombre est conservé, pour pouvoir le montrer au client. Aucune inférence n'est faite à partir de ces transactions. |
| **Consentement par famille** | 4 familles : transactions, usage de l'app, produits, profil. Une famille coupée **n'est pas calculée** (privacy by design, pas un simple filtre à l'affichage). Test : `test_consent_withdrawal_removes_signal_family`. |
| **Base légale distincte pour la fraude** | La protection anti-arnaque repose sur la prévention de la fraude, pas sur le consentement marketing : elle reste active même si tout est coupé, et le panneau « pourquoi » le dit. Test : `test_fraud_prevention_ignores_marketing_consent`. |
| **Pas de décision automatique à effet juridique (art. 22)** | Aucune action n'accorde ni ne refuse un crédit. Les actions liées au crédit ne font que reprendre une simulation ou proposer un rendez-vous, et le panneau « pourquoi » indique qu'une personne décide. |
| **Transparence (art. 13 à 15)** | Chaque message a un « pourquoi je vois ça » généré à partir du journal du moteur, pas par le LLM. |
| **Minimisation** | Le moteur ne voit qu'un snapshot agrégé. Le LLM ne reçoit que l'action, un texte de référence, la langue, le ton et une tranche d'âge : **aucune transaction, aucun montant, aucun identifiant**. Test : `test_llm_path_cached_and_personalized`. |
| **Pseudonymisation du feedback** | `action_events` utilise un HMAC-SHA256 de l'identifiant client avec un sel aléatoire stocké en base, jamais dans le code. |
| **Droit d'opposition** | « Ne plus voir ça » supprime définitivement une action pour ce client ; « Pas maintenant » la met en pause 30 jours. Un refus ne peut pas être effacé par une réaction positive ultérieure. |
| **Données synthétiques** | Aucune donnée réelle dans le repo. `.env`, `.demo_credentials` et la base sont ignorés par git. |

## Ce que le client voit

- Onglet **Mes données** : un interrupteur par famille, et une ligne « Prévention de la fraude : toujours actif ».
- Panneau **Pourquoi je vois ça ?** : les preuves utilisées (« Achats récents dans des magasins pour bébé »…), la base légale, le nombre de transactions sensibles exclues, et un lien vers la gestion des données.

## Limites connues

- Les libellés de virement (« naissance ») sont une donnée de communication : en production, leur usage devrait être encadré (catégorisation en amont, pas de lecture libre du texte).
- Le lien familial entre clients (grands-parents et parents) n'est pas utilisé : seuls les virements du client lui-même comptent.
- Une analyse d'impact (AIPD) serait nécessaire avant une mise en production.
