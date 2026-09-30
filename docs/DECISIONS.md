# Decision log

Each entry: context, choice, reason.

## D1. The LLM shapes, it never decides
**Choice:** deterministic decision (rules + score + guardrails), LLM only to rewrite a reference text.
**Why:** auditability (line-by-line journal), compliance (art. 22), cost at 2.3 M customers, security (the LLM cannot inject anything).

## D2. The LLM only produces text
**Choice:** the LLM returns `{title, body, push, checklist_title, checklist}`; the server assembles blocks, buttons, delivery and the "why" panel.
**Why:** the LLM can neither invent a button, nor lie about the data used, nor inject HTML.

## D3. Abstaining is an action
**Choice:** a sixth action family, shown to the customer with its reason.
**Why:** it is what separates a relationship from a campaign, and it can be demonstrated (Thomas).

## D4. Financial stress ≥ 2: no sales, help first
**Choice:** hard guardrail + arbitration that prioritises "Accompany", except fraud protection.
**Why:** the key demo moment (Emma / Sofia), and an ethical commitment that doesn't depend on a weight.

## D5. Consent = do not compute
**Choice:** a switched-off family is not extracted at all in the snapshot.
**Why:** privacy by design, stronger than a display filter, and visible behind the scenes.

## D6. Fraud prevention outside marketing consent
**Choice:** `scam_risk` uses age and the pending transfer even if everything is switched off; the "why" panel says so.
**Why:** protecting a customer must not depend on a marketing opt-in. Legal basis to validate with the DPO.

## D7. Generic text per segment, cached
**Choice:** key `action × segment × language × tone × format`, `{first_name}` inserted by the server.
**Why:** a couple of thousand texts for the whole base; the cost does not grow with the number of customers.

## D8. Learning capped at 30%, bandit on tone only
**Why:** learn without ever letting optimisation override a guardrail; optimise value (completed action), not clicks.

## D9. Four channels, one phone screen per channel
**Choice:** the engine returns a `delivery` object; the front end draws a lock screen (push), an incoming call (voice), an app card, or an advisor booking panel.
**Why:** the channel is part of the decision, so the demo must *show* it, not just label it. One persona per channel (Lucas added for push).

## D10. Typed human-in-the-loop tasks
**Choice:** five task types (outreach, callback, appointment, credit review, fraud review), each with its own allowed actions, validated on the server, with an audit trail; bookings convert an outreach task instead of creating a second one.
**Why:** "a person decides" only means something if what the person can do is coherent with the situation — and if it is traceable.

## D11. Everything in English, content in three languages
**Choice:** code, comments, docs and default interface in English; interface and customer content switchable to French and Dutch; the language is stored as the customer's preference.
**Why:** English for a mixed jury and codebase; FR/NL because Belgium.

## D12. Security: identity only from the token, Host header allow-listed
**Choice:** no `customer_id` in customer routes, 404 on another customer's resource; exact dependency pins (Starlette 1.7.0), `TrustedHostMiddleware`, raw scope path in middleware.
**Why:** remove whole classes of bugs (IDOR, Host header bypass) rather than check case by case.

## D13. Demo clock fixed, except for the scam pause
**Choice:** `DEMO_NOW` for the data; the real clock for `hold_until`.
**Why:** reproducible demo, and a pause you can actually watch count down.

## D14. Stack
FastAPI, SQLite, vanilla front end (no build chain, strict CSP), Gemini (optional, GCP credits), ElevenLabs (optional, low-digital customers only, cached).
