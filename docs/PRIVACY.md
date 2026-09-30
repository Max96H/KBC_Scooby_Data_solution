# Privacy and compliance

> Design analysis for a PoC, not legal advice. Legal bases are to be validated with the DPO.

## Principles applied in the code

| Principle | Implementation |
| --- | --- |
| **Special categories excluded (GDPR art. 9)** | `engine/sensitive.py` removes health (pharmacy, doctor, hospital, mental health), beliefs (religious donations, places of worship), political opinions, trade unions and orientation **before** any computation. Only their count is kept, so it can be shown to the customer. Nothing is ever inferred from these transactions. |
| **Consent per family** | 4 families: transactions, app usage, products, profile. A switched-off family **is not computed** (privacy by design, not a display filter). Test: `test_consent_withdrawal_removes_signal_family`. |
| **Separate legal basis for fraud** | Scam protection relies on fraud prevention, not marketing consent: it stays on even if everything is switched off, and the "why" panel says so. Test: `test_fraud_prevention_ignores_marketing_consent`. |
| **No automated decision with legal effect (art. 22)** | No action grants or refuses credit. Credit-related actions only resume a simulation or offer a meeting; a booking on a credit topic becomes a *credit review* task handled by a person. |
| **Transparency (art. 13–15)** | Every message has a "why am I seeing this" built from the engine journal, not by the LLM, in the customer's language. |
| **Minimisation** | The engine only sees an aggregated snapshot. The LLM only receives the action, a reference text, the language, the tone and an age band: **no transaction, no amount, no identifier**. Test: `test_llm_path_cached_and_personalized`. |
| **Pseudonymised feedback** | `action_events` uses an HMAC-SHA256 of the customer id with a random salt stored in the database, never in the code. |
| **Right to object** | "Don't show again" suppresses an action permanently for that customer; "Not now" pauses it for 30 days. A refusal cannot be erased by a later positive reaction. |
| **Language choice** | The customer (or presenter) picks EN / FR / NL; stored as a preference, used for all content. |
| **Synthetic data** | No real data in the repo. `.env`, `.demo_credentials` and the database are ignored by git. |

## What the customer sees

- **My data** tab: one switch per family, and a "Fraud prevention: always on" line.
- **Why am I seeing this?** panel: the evidence used ("Recent purchases in baby stores"…), the legal basis, the number of sensitive transactions excluded, and a link to manage the data.

## Known limits

- Transfer communications ("birth") are communication data: in production their use should be framed (upstream categorisation, no free reading of the text).
- Family links between customers (grandparents and parents) are not used: only the customer's own transfers count.
- A data protection impact assessment (DPIA) would be needed before production.
