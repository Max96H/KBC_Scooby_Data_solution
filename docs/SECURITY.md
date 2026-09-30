# Security

Security is 10% of the score. It is assessed by **Aikido's AI Code Audit**, which focuses on four categories: **business logic**, **IDOR**, **authentication**, **authorisation**. Every control below is implemented **and tested** (`tests/test_security.py`, `tests/test_engine.py`).

## Aikido findings and fixes

The baseline audit reported two findings, both about the same issue in the framework dependency.

| # | Finding | Root cause | Fix | Tests |
| --- | --- | --- | --- | --- |
| 1 | **Host header injection in Starlette < 1.0.1** (security bypass): `request.url` is rebuilt from the Host header while routing uses the raw path, so a crafted Host can make `request.url.path` differ from the real path | `requirements.txt` only pinned `fastapi>=0.115`, which allowed a vulnerable Starlette | **Starlette pinned to 1.7.0** (and every dependency pinned exactly) | `test_patched_starlette_version` |
| 2 | **Host header injection in Starlette 0.38.6** (same class: `/`, `?`, `#` injected in the Host header to confuse path-based checks) | Same | Same upgrade, plus two defence-in-depth measures below | `test_malicious_host_header_rejected`, `test_security_decisions_do_not_use_request_url` |

Defence in depth, so that the class of bug cannot come back even with a future regression:

1. **`TrustedHostMiddleware`** with an explicit allow-list (`ALLOWED_HOSTS`, default `localhost,127.0.0.1`). Any request with another Host header — including `localhost/admin?` or `host@evil.com` — is rejected with 400 before reaching the application.
2. **No security decision uses the reconstructed URL.** The only path-based logic in a middleware (the `Cache-Control: no-store` header on the API) reads the raw ASGI `scope["path"]`. Authorisation is never path-based anyway: it is done per route with dependencies (`require_customer`, `require_advisor`).

Steps to close them in Aikido: push, re-run the audit, mark both findings as resolved, take the "after" screenshot.

## Controls per Aikido category

### Authentication

| Threat | Control | Where | Test |
| --- | --- | --- | --- |
| Password theft | PBKDF2-HMAC-SHA256, 200,000 iterations, random salt, constant-time comparison | `security.py` | – |
| Hard-coded passwords | None: `DEMO_PASSWORD` from the environment, otherwise random passwords written to `.demo_credentials` (not versioned, `chmod 600`) | `data/generate.py` | – |
| Account enumeration | Same message, same code and same computation time (dummy hash) for an unknown account | `routes/auth.py` | `test_login_wrong_password_and_unknown_user_look_identical` |
| Brute force | 5 attempts per IP and per username over 5 minutes → HTTP 429 | `security.py` | `test_login_rate_limited` |
| Forged token | HS256 JWT, algorithm enforced (`none` refused), expiry mandatory, key from `SECRET_KEY` (random if missing, never a default value) | `security.py`, `config.py` | `test_forged_tokens_rejected` |
| Token of a deleted account | Every request re-checks that the account exists with the same role | `security.py` | `test_deleted_user_token_revoked` |
| CSRF | Token in the `Authorization` header, no cookie | `common.js` | – |

### Authorisation

| Threat | Control | Test |
| --- | --- | --- |
| Customer calling advisor endpoints | `require_customer` / `require_advisor` dependencies on every route | `test_customer_cannot_use_advisor_endpoints`, `test_advisor_has_no_customer_view` |
| Role escalation through the token | Role and customer in the token must match the database | `test_token_cannot_escalate_role_or_switch_customer` |
| Advisor browsing any customer | Detailed journal only when a task exists for that customer (least privilege) | `test_advisor_journal_requires_a_task` |
| Advisor action not fitting the task | Allowed actions per task type, validated on the server; closed tasks are read-only | `test_advisor_actions_must_match_task_type` |
| Engine journal exposed in production | `DEMO_MODE=false` removes it from customer responses | – |

### IDOR

| Threat | Control | Test |
| --- | --- | --- |
| Read or change another customer's decision | **No customer endpoint takes a `customer_id`**: identity comes from the token. Every decision access goes through `owned_decision()` which filters on `id AND customer_id`. Another customer's resource returns 404 (not 403, to avoid revealing it exists) | `test_idor_on_every_decision_endpoint` |
| Cancel or list someone else's appointment | Appointment queries filter on the token's customer | `test_cannot_cancel_someone_elses_appointment` |
| Change another customer's consent or language | Writes use the token's `customer_id` only | `test_consent_and_language_only_change_own_data` |
| Passing a `customer_id` parameter | Ignored | `test_no_endpoint_accepts_customer_id` |
| Guessable identifiers | Decisions are UUID v4 (128 bits), format validated | `test_strict_input_validation` |

### Business logic

| Threat | Control | Test |
| --- | --- | --- |
| Forcing an action through a parameter | The customer never sends an `action_id`; a button is only accepted if it belongs to the action of **that** decision (closed catalogue) | `test_cannot_trigger_cta_of_another_action` |
| Bypassing the scam pause | `hold_until` is set and checked on the server with the real clock; confirming early → 409 | `test_scam_hold_cannot_be_bypassed` |
| Inflating an action's score | `completed` is only set by the server; the customer can only send `seen`, `clicked`, `not_now`, `never`, `intrusive` | `test_client_cannot_self_report_completed` |
| Erasing a refusal | A refusal cannot be replaced by a positive reaction | `test_positive_reaction_cannot_erase_refusal` |
| Booking abuse | Only from a message offering an appointment, one active appointment per customer, no past slot, no unknown mode | `test_booking_rules`, `test_past_slot_cannot_be_booked` |
| Double booking (race condition) | Partial unique index in the database: one `booked` appointment per slot | `test_double_booking_blocked_by_database` |
| Releasing a transfer without checks | Only on a fraud task, only for a pending/held transfer, note mandatory | `test_fraud_hold_creates_urgent_review_and_advisor_can_block` |
| Selling to a customer in difficulty | Deterministic guardrail, not influenced by learning | `test_same_signal_opposite_decision` |

## Other controls

| Topic | Control |
| --- | --- |
| Dependencies | Every dependency pinned exactly (`requirements.txt`), Starlette ≥ 1.0.1 |
| Host header | `TrustedHostMiddleware` allow-list |
| SQL injection | 100% parameterised queries, no concatenation |
| Input validation | Pydantic with `extra="forbid"`, bounded lengths and regexes, `Literal` for enumerations (actions, reactions, modes, languages) |
| Request size | 16 KB max (413) |
| XSS | Front end without `innerHTML` (DOM + `textContent`); CSP `default-src 'self'; script-src 'self'`; no inline script or style |
| LLM output | JSON schema constrained on the Gemini side, then revalidated: no tag, no URL, no template other than `{first_name}`, no invented figures; the LLM only produces text, the server builds the structure. On failure: template |
| Prompt injection | The LLM receives no customer-provided data (no label, no free text) |
| Headers | CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, COOP, `Cache-Control: no-store` on the API |
| CORS | Explicit origin list, no credentials |
| Error leaks | Global handler: `{"detail": "Internal error"}`, trace only in logs |
| API docs | `/docs` disabled by default (`ENABLE_DOCS`) |
| Secrets | `.env`, `.demo_credentials`, `*.db` in `.gitignore`; `.env.example` without values; pseudonymisation salt generated in the database |
| Container | Non-root user |
| CI | GitHub Actions runs the tests on every push, read-only permissions |

## Accepted limits (PoC)

- Login rate limiting in memory (single instance). Production: Redis or API gateway.
- No individual token revocation before expiry (60 min). Production: revocation list or short tokens + refresh.
- `X-Forwarded-For` deliberately ignored: behind a proxy, configure `--proxy-headers` with trusted proxies.
- Password authentication for the demo. Production: the bank's strong authentication.

## Aikido procedure

1. Create the account with the hackathon link → **Continue with GitHub**.
2. Connect the **public** hackathon repo.
3. Run the **AI Code Audit** (baseline). Take the **"before"** screenshot → `docs/aikido/before.png`.
4. Fix, add a test when possible, mark as **resolved** in Aikido, log it below.
5. Re-run the audit, take the **"after"** screenshot → `docs/aikido/after.png`.

### Fix log

| # | Finding | Category | Fix | Commit |
| --- | --- | --- | --- | --- |
| 1 | Host header injection, Starlette < 1.0.1 | Dependency / security bypass | Starlette 1.7.0 pinned, TrustedHostMiddleware, scope path | |
| 2 | Host header injection, Starlette 0.38.6 | Dependency / security bypass | Same | |
