# The decision engine

Code: `app/engine/signals.py`, `app/engine/decision.py`, `app/engine/catalog.py`.

## 1. Derived signals

Each signal has a **value**, a **confidence** between 0 and 1, the **data families** used (for consent) and **evidence** codes (translated in EN/FR/NL for the "why" panel).

| Signal | Rule (simplified) | Confidence |
| --- | --- | --- |
| `life_event = baby` | baby-store purchases (60 d) +0.45, ≥ 3 purchases +0.10; "family insurance" simulation +0.35; household aged 22–45 +0.10 | max 0.95 |
| `life_event = grandchild` | "birth" transfer +0.50; monthly family transfer for 3 months +0.25; aged 55+ +0.15 | |
| `life_event = first_job` | first salary of the half-year 0.65; student account +0.15; aged ≤ 27 +0.10 | |
| `life_event = income_loss` | salary present ≥ 4 of 5 months, missing for more than 38 days | 0.70 |
| `life_event = housing` | notary or moving costs +0.50; abandoned loan simulation +0.35; ≥ 3 visits of loan pages +0.20 | |
| `life_event = retirement` | aged 60–66 and a loan ending within the year | 0.70 |
| `financial_stress` (0–3) | +1 balance down 3 months in a row; +1 savings going down; +1 at least 2 late fees in 90 d; +1 overdraft forecast (if already ≥ 1) | 0.6 + 0.1 × level |
| `overdraft_risk` | balance − recurring debits expected within 7 d < 0 | 0.80 |
| `intent = mortgage` | abandoned loan simulation, +0.3 if ≥ 3 visits | 0.5 to 0.8 |
| `scam_risk` | new beneficiary 0.35; ≥ €2,000 +0.30; aged 65+ +0.20; crypto platform +0.25 | legal basis: fraud prevention |
| `deadline` | fixed rate ending ≤ 120 d; car insurance ≤ 30 d | 0.90 |
| `calendar = pension_tax` | pension savings with remaining allowance, October to December | 0.65 |
| `channel_pref` | low digital and inactive → voice; active or very digital → app; otherwise push | |

## 2. From signals to candidate actions

| Signal | Candidate actions |
| --- | --- |
| baby | `family_insurance_review` (Propose), `family_budget_support` (Accompany, **only if stress ≥ 1**) |
| grandchild | `grandchild_savings_info` (Inform) |
| first job | `first_salary_budget` (Inform), `student_to_standard` (Simplify, if student account) |
| income loss | `job_loss_support` (Accompany, no credit offer) |
| housing / intent | `loan_simulation_resume` (Simplify, credit: human required) |
| retirement | `retirement_planning` (Accompany) |
| overdraft likely | `overdraft_alert` (Protect) |
| scam | `scam_pause` or `crypto_verification` (Protect) |
| deadlines | `fixed_rate_end_review`, `car_insurance_renewal` |
| calendar | `pension_savings_tax` |

When several signals lead to the same action, the most confident one is kept.

## 3. The score

```
score_base  = 0.35·customer_value + 0.25·urgency + 0.20·confidence + 0.10·bank_value − 0.10·sensitivity
score_final = score_base × (0.7 + 0.3 × efficiency)        efficiency ∈ [0, 1], 0.5 without history
```

**Ethical choice:** customer value weighs 3.5 times more than bank value. Learning (efficiency) never weighs more than 30%.

Each action's attributes (customer value, bank value, urgency, sensitivity, commercial or not, legal basis, sensitive topic, credit) are in `catalog.py`.

## 4. Guardrails (in order)

| # | Rule | Effect | Code |
| --- | --- | --- | --- |
| 1 | **Consent**: a switched-off data family is not computed; a candidate that would depend on it is set aside | blocks | `consent_withdrawn` |
| 2 | **Confidence ≥ 0.6** to act | blocks | `low_confidence` |
| 3 | **Financial stress ≥ 2 → no sales** | blocks commercial actions | `financial_stress_no_sales` |
| 4 | **Refusal respected**: 30-day pause after "not now", permanent after "don't show again" | blocks | `suppressed_after_refusal` |
| 5 | **Stress ≥ 2 → help comes first** (except fraud protection) | arbitration | `stress_prioritizes_help` |
| 6 | **One action at a time** | arbitration | `one_action_at_a_time` |
| 7 | **At most 1 proactive message (push, voice) per 7 days** | channel falls back to the app | `frequency_cap` |
| 8 | **Quiet hours 9 pm – 8 am**: no notification or call, except protection | channel falls back to the app | `quiet_hours` |
| 9 | **Credit: never an automated decision** (GDPR art. 22) | the action can only resume a simulation or offer a meeting | `credit_human_in_the_loop` |

If no candidate survives, the engine **abstains** with an explicit reason (`no_signal`, `low_confidence`, `stress_no_sales`, `all_blocked`), shown to the customer.

## 5. The channel

See [CHANNELS.md](CHANNELS.md): rules, reason codes and what the customer sees on each channel.

## 6. Worked examples (no feedback history: efficiency 0.5 → × 0.85)

**Emma**: `life_event = baby`, confidence 0.95 (baby purchases, 4 purchases, simulation, young household).

| Candidate | Base | Final | Status |
| --- | --- | --- | --- |
| `family_insurance_review` | 0.35·0.8 + 0.25·0.6 + 0.20·0.95 + 0.10·0.5 − 0.10·0.3 = **0.640** | 0.544 | **chosen** |

`family_budget_support` is not even a candidate (stress = 0). Channel: app (active customer).

**Sofia**: same baby signal (confidence 0.65, no simulation), but stress = 3.

| Candidate | Base | Final | Status |
| --- | --- | --- | --- |
| `family_budget_support` | 0.35·0.95 + 0.25·0.85 + 0.20·0.65 + 0.10·0.1 − 0.10·0.6 = **0.625** | 0.531 | **chosen** |
| `family_insurance_review` | 0.580 | 0.493 | **blocked**: stress ≥ 2, no sales |

Channel: advisor (sensitive topic). An *outreach* task is created in the advisor queue, and Sofia can book a time directly.

**Lucas**: `overdraft_risk` (0.80), no stress. `overdraft_alert`: base 0.628. Channel: push (urgent 0.8, app not opened for 20 days, medium digital).

**Marcel**: `scam_risk = transfer` (0.85). `scam_pause`: base 0.770. Channel: voice (low digital). The transfer goes on hold for 10 minutes, an urgent *fraud review* task is created, and confirming before the end of the hold is refused by the server (HTTP 409).

**Thomas**: no signal. **Abstention** (`no_signal`), shown: "Nothing for you today".

The scores shown live in the demo are slightly different, because the simulated feedback moves the efficiency term.

## 7. The journal

Every decision produces a journal (stored with the decision): consents, excluded transactions, signals, candidates with scores and reasons, guardrails, decision, channel and reason code, text source, language, bandit draws. It feeds the "why" panel (readable version for the customer), the behind-the-scenes panel (demo) and audits (advisor).
