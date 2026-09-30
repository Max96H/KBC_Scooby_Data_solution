# Journal des décisions

Chaque décision : contexte, choix, raison. Les points ouverts du document de départ (section 12) sont tranchés ici.

## D1. Le LLM met en forme, il ne décide jamais
**Choix :** décision déterministe (règles + score + garde-fous), LLM uniquement pour reformuler un texte de référence.
**Pourquoi :** auditabilité (journal ligne par ligne), conformité (art. 22), coût à 2,3 M clients, sécurité (le LLM ne peut rien injecter).

## D2. Le LLM ne produit que du texte
**Choix :** le LLM renvoie `{title, body, checklist_title, checklist}` ; le serveur assemble les blocs, les boutons et le panneau « pourquoi ».
**Pourquoi :** le LLM ne peut ni inventer un bouton, ni mentir sur les données utilisées, ni injecter de HTML. Plus strict que « le LLM renvoie des blocs ».

## D3. S'abstenir est une action
**Choix :** 6ᵉ famille d'actions, affichée au client avec sa raison.
**Pourquoi :** c'est ce qui distingue une relation d'une campagne, et ça se démontre (Thomas).

## D4. Stress financier ≥ 2 : aucune vente, l'aide d'abord
**Choix :** garde-fou dur + arbitrage qui donne la priorité à « Accompagner », sauf protection anti-fraude.
**Pourquoi :** le moment fort de la démo (Emma / Sofia), et un engagement éthique qui ne dépend pas d'un poids.

## D5. Consentement = ne pas calculer
**Choix :** une famille coupée n'est pas extraite du tout dans le snapshot.
**Pourquoi :** privacy by design, plus fort qu'un filtre à l'affichage, et vérifiable dans les coulisses.

## D6. Prévention de la fraude hors consentement marketing
**Choix :** `scam_risk` utilise l'âge et le virement en attente même si tout est coupé ; le panneau « pourquoi » l'annonce.
**Pourquoi :** protéger un client ne doit pas dépendre d'un opt-in marketing. Base légale à valider avec le DPO.

## D7. Texte générique par segment, mis en cache
**Choix :** clé `action × segment × langue × ton × format`, `{first_name}` inséré par le serveur.
**Pourquoi :** quelques milliers de textes pour toute la base ; le coût ne croît pas avec le nombre de clients.

## D8. Apprentissage borné à 30 %, bandit sur le ton uniquement
**Pourquoi :** apprendre sans jamais laisser l'optimisation contourner un garde-fou ; optimiser la valeur (action complétée), pas le clic.

## D9. Stack (section 12, tranché)
- **Back :** FastAPI (validation Pydantic, rapide à écrire).
- **Front :** HTML/JS sans framework : aucune chaîne de build, CSP stricte, rien à installer pour le jury.
- **Base :** SQLite (zéro installation).
- **LLM :** Gemini via les crédits GCP, sortie JSON contrainte (`responseSchema`), optionnel.
- **Voix :** ElevenLabs **oui**, limitée aux clients peu digitaux (Jan & Monique, Marcel), audio mis en cache, repli sur la voix du navigateur.

## D10. Nom du projet
**Moments** : on ne parle plus de campagnes, on parle de moments de vie.

## D11. Sécurité : l'identité ne vient que du token
**Choix :** aucun `customer_id` dans les routes client ; 404 (pas 403) sur la ressource d'un autre client.
**Pourquoi :** supprime la classe entière des IDOR plutôt que de la vérifier au cas par cas.

## D12. Horloge de démo fixe, sauf pour la pause anti-arnaque
**Choix :** `DEMO_NOW` pour les données ; horloge réelle pour `hold_until`.
**Pourquoi :** démo reproductible, et une pause qu'on voit vraiment défiler.

## Points restant ouverts
- Répartition dans l'équipe : voir [SUBMISSION.md](SUBMISSION.md).
- Calibration des poids sur des données réelles (hors hackathon).
