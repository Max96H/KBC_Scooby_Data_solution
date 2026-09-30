# Human in the loop

Code: `app/engine/hitl.py`, `app/routes/advisor.py`, advisor console `static/dashboard.*`.

**The engine proposes, a person decides.** Sensitive topics, credit and fraud checks always end up with an advisor, and every advisor action is typed, validated on the server and recorded.

## Where tasks come from

| Trigger | Task type | Reason code | Priority |
| --- | --- | --- | --- |
| Engine picks the *advisor* channel for a sensitive topic (Sofia) | `outreach` | `engine_outreach` | normal |
| Customer presses "Have an advisor call me back" (Jan) | `callback` | `customer_callback` | normal |
| Customer books an appointment in the app | `appointment` (or `credit_review` for credit topics) | `customer_booking` | normal |
| A transfer is put on a safety hold (Marcel) | `fraud_review` | `fraud_hold` | **high** |
| Customer presses "Talk to someone now" during a hold | `fraud_review` | `customer_fraud_call` | **high** |
| First crypto transfer | `fraud_review` | `crypto_verification` | normal |

No duplicates: an open task of the same type for the same customer and action is reused (and upgraded to high priority if needed).

## What an advisor can do, per task type

| Task type | Allowed actions |
| --- | --- |
| `outreach` | log a call (reached / no answer), book an appointment for the customer, dismiss (note required) |
| `callback` | log a call, book an appointment, dismiss |
| `appointment` | meeting completed (note required), customer did not come, cancel |
| `credit_review` | same as appointment, with a reminder that Moments never grants or refuses credit |
| `fraud_review` | block the transfer, release the transfer (note required), log a call |

Rules enforced on the server:
- any action outside the list for the task type is refused (409);
- a closed task cannot be acted on again;
- a note is required to dismiss, complete or release a transfer;
- "log a call: reached" closes an outreach / callback task, "no answer" keeps it open;
- booking from an outreach or callback **converts** that task into an appointment (one lifecycle, one history);
- releasing or blocking needs a transfer that is actually pending or on hold.

## Appointments

- Advisor availability: `appointment_slots` (7 working days, 9:00–16:00, lunch break), generated with the demo data.
- Modes: phone, video, branch.
- A customer can only book from a message that offers an appointment, can have **one active appointment** at a time, and cannot book a slot in the past.
- A slot cannot be booked twice: checked in the code **and** enforced by a partial unique index in the database (race-proof).
- A customer can only see and cancel their own appointments (IDOR tests).
- Cancelling closes the linked task (`cancelled_by_customer`).

## Coherence with the customer side

| Customer action | Effect in the console |
| --- | --- |
| Books a time (Sofia) | Outreach task becomes an *appointment*, shown in the agenda |
| Cancels the transfer during the hold (Marcel) | Fraud review closed as `customer_cancelled` |
| Confirms after the hold | Fraud review closed as `customer_confirmed` |
| Asks for a callback (Jan) | New *callback* task |

And the other way round: when the advisor completes a meeting or blocks a scam, the action that started it gets the best feedback (`completed`), which feeds the learning loop.

## Audit trail

Every task keeps a history in `task_events`: creation (with reason), calls, bookings, closure (with outcome and note), with who did it (`engine`, `customer`, or the advisor's username) and when. The console shows it as a timeline.

## Least privilege

- An advisor only sees the detailed engine journal of a customer for whom a task exists.
- Customers cannot call any advisor endpoint (403), advisors cannot call customer endpoints (403).
- Metrics are aggregated and pseudonymised.
