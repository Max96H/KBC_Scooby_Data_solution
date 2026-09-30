# API

Base: `http://localhost:8000`. Every API response has `Cache-Control: no-store`. Authentication: `Authorization: Bearer <token>`.
Requests whose `Host` header is not in `ALLOWED_HOSTS` are rejected with 400.
`/docs` (Swagger) is disabled by default; `ENABLE_DOCS=true` turns it on locally.

## Authentication

### `POST /api/auth/login`
```json
{ "username": "emma", "password": "..." }
```
→ `200 { token, token_type, expires_in, role, display_name, first_name, language }`
Errors: `401` invalid credentials (same message for an unknown account), `422` format, `429` too many attempts.

## Customer (`role = customer`)

Identity **always** comes from the token. No endpoint accepts a `customer_id`.

| Method | Route | Body | Response |
| --- | --- | --- | --- |
| GET | `/api/me` | – | minimal profile, username, balance, demo date |
| PUT | `/api/me/language` | `{ "language": "en" \| "fr" \| "nl" }` | preferred language for all content |
| GET | `/api/me/feed` | – | `{ decision_id, screen, journal, active_appointment }` (journal absent when `DEMO_MODE=false`) |
| POST | `/api/me/decisions/{decision_id}/cta` | `{ "cta_id": "start_review" }` | `{ ok, effect, message }`; `404` if the decision is not yours or the button does not belong to this action; `409` scam pause in progress |
| POST | `/api/me/decisions/{decision_id}/feedback` | `{ "reaction": "clicked" \| "seen" \| "not_now" \| "never" \| "intrusive" }` | `{ ok }`; `409` on an abstention |
| POST | `/api/me/decisions/{decision_id}/why` | – | records that the "why" panel was opened |
| GET | `/api/me/decisions/{decision_id}/voice` | – | `audio/mpeg` (ElevenLabs) or `204` (the front end uses the browser voice) |
| GET | `/api/me/consents` | – | `[{ family, enabled }]` |
| PUT | `/api/me/consents/{family}` | `{ "enabled": false }` | updated list; `404` unknown family |
| GET | `/api/me/slots` | – | next available advisor slots |
| GET | `/api/me/appointments` | – | the customer's appointments |
| POST | `/api/me/appointments` | `{ "decision_id", "slot_id", "mode": "phone" \| "video" \| "branch" }` | `{ ok, message }`; `409` message without an appointment offer, slot in the past or taken, already an active appointment |
| POST | `/api/me/appointments/{id}/cancel` | – | `{ ok, message }`; `404` if not yours |

`decision_id`: 32 hexadecimal characters (otherwise `422`).

### Screen format

```json
{
  "action_id": "overdraft_alert",
  "family": "protect",
  "channel": "push",
  "language": "en",
  "tone": "direct",
  "bookable": true,
  "delivery": { "channel": "push", "title": "Heads up: likely overdraft in the next few days", "text": "Your balance may go below zero this week. Tap to act." },
  "blocks": [
    { "type": "highlight", "title": "...", "body": "...", "ctas": [{ "id": "shift_payment", "label": "Move a payment", "effect": "complete" }] },
    { "type": "checklist", "title": "...", "items": ["..."] },
    { "type": "why_panel", "title": "Why am I seeing this?", "signals_used": ["..."], "families": ["transactions"], "legal_basis": "consent", "notes": ["..."] }
  ]
}
```

`delivery.channel` is one of `app`, `push`, `voice`, `human`; `push` and `voice` carry a title and a text (the notification text, or the script read aloud). Block types: `highlight`, `checklist`, `why_panel`, `transfer_hold`, `human`, `abstain`. The front end ignores any other type. Button effects: `complete`, `ack`, `book`, `callback`, `fraud_call`, `cancel_transfer`, `confirm_transfer`.

## Advisor (`role = advisor`)

| Method | Route | Response |
| --- | --- | --- |
| GET | `/api/advisor/tasks` | queue with type, priority, reason, `allowed_actions`, appointment, transfer, history |
| POST | `/api/advisor/tasks/{id}/actions` | `{ action, note?, outcome?, slot_id?, mode? }` → `{ ok }`; `409` action not allowed for this task type, task closed, note missing, slot taken; `404` unknown task |
| GET | `/api/advisor/slots` | available slots |
| GET | `/api/advisor/appointments` | upcoming booked appointments |
| GET | `/api/advisor/decisions/{decision_id}` | full journal; `404` if no task exists for this customer |
| GET | `/api/advisor/metrics` | totals, efficiency per action × segment, channel mix, bandit, fairness per age band, daily curve, render cache |

Actions: `log_call` (with `outcome`: `reached` / `no_answer`), `book_appointment` (with `slot_id`, `mode`), `dismiss`, `complete`, `no_show`, `cancel_appointment`, `release_transfer`, `block_transfer`. See [HUMAN_IN_THE_LOOP.md](HUMAN_IN_THE_LOOP.md) for which ones apply to which task type.

## Misc

| Method | Route | Response |
| --- | --- | --- |
| GET | `/api/health` | `{ status, llm, voice, demo_mode }` |
| GET | `/` | customer demo |
| GET | `/advisor` | advisor console |
