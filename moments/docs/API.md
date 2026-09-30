# API

Base : `http://localhost:8000`. Toutes les réponses d'API ont `Cache-Control: no-store`. Authentification : `Authorization: Bearer <token>`.
`/docs` (Swagger) est désactivé par défaut ; `ENABLE_DOCS=true` l'active en local.

## Authentification

### `POST /api/auth/login`
```json
{ "username": "emma", "password": "..." }
```
→ `200 { token, token_type, expires_in, role, display_name, first_name, language }`
Erreurs : `401` identifiants invalides (message identique pour un compte inexistant), `422` format, `429` trop de tentatives.

## Client (`role = customer`)

L'identité vient **toujours** du token. Aucun endpoint n'accepte de `customer_id`.

| Méthode | Route | Corps | Réponse |
| --- | --- | --- | --- |
| GET | `/api/me` | – | profil minimal, solde, date de démo |
| GET | `/api/me/feed` | – | `{ decision_id, screen, journal }` (journal absent si `DEMO_MODE=false`) |
| POST | `/api/me/decisions/{decision_id}/cta` | `{ "cta_id": "start_review" }` | `{ ok, effect, message }` ; `404` si la décision n'est pas à vous ou si le bouton n'appartient pas à cette action ; `409` pause anti-arnaque en cours |
| POST | `/api/me/decisions/{decision_id}/feedback` | `{ "reaction": "clicked" \| "seen" \| "not_now" \| "never" \| "intrusive" }` | `{ ok }` ; `409` sur une abstention |
| POST | `/api/me/decisions/{decision_id}/why` | – | enregistre l'ouverture du panneau « pourquoi » |
| GET | `/api/me/decisions/{decision_id}/voice` | – | `audio/mpeg` (ElevenLabs) ou `204` (le front utilise la voix du navigateur) |
| GET | `/api/me/consents` | – | `[{ family, label, enabled }]` |
| PUT | `/api/me/consents/{family}` | `{ "enabled": false }` | liste mise à jour ; `404` famille inconnue |

`decision_id` : 32 caractères hexadécimaux (sinon `422`).

### Format de l'écran (`screen`)

```json
{
  "action_id": "family_insurance_review",
  "family": "propose", "family_label": "Proposer",
  "channel": "app", "language": "fr", "tone": "warm",
  "blocks": [
    { "type": "highlight", "title": "...", "body": "...", "ctas": [{ "id": "start_review", "label": "..." }] },
    { "type": "checklist", "title": "...", "items": ["..."] },
    { "type": "why_panel", "title": "Pourquoi je vois ça ?", "signals_used": ["..."], "families": ["transactions"], "legal_basis": "consent", "notes": ["..."] }
  ]
}
```

Types de blocs possibles : `highlight`, `checklist`, `why_panel`, `transfer_hold`, `voice`, `human`, `abstain`. Le front ignore tout autre type.

## Conseiller (`role = advisor`)

| Méthode | Route | Réponse |
| --- | --- | --- |
| GET | `/api/advisor/tasks` | file d'attente (client, action, famille, motif, statut) |
| POST | `/api/advisor/tasks/{id}/done` | clôture ; `404` si inexistante ou déjà clôturée |
| GET | `/api/advisor/decisions/{decision_id}` | journal complet ; `404` si aucune tâche n'existe pour ce client |
| GET | `/api/advisor/metrics` | totaux, efficacité par action × segment, bandit, équité par tranche d'âge, courbe journalière, cache de rendu |

## Divers

| Méthode | Route | Réponse |
| --- | --- | --- |
| GET | `/api/health` | `{ status, llm, voice, demo_mode }` |
| GET | `/` | démo client |
| GET | `/conseiller` | espace conseiller |
