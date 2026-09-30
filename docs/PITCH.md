# Pitch

## Short description (Builderbase, about 80 words)

> **Moments** replaces campaigns with one decision per customer and per life moment. A deterministic engine detects the moment (new baby, first salary, scam in progress, financial pressure), picks **one** useful action and the right channel — app card, push notification, voice call or an advisor — and always explains why, in English, French or Dutch. The same signal can lead to opposite decisions, and when nothing is useful, Moments abstains. The LLM shapes, it never decides: auditable, compliant, and 2.3 M customers decided in about a minute.

## 60-second pitch

Today a bank talks to its customers through campaigns: a segment, a message, a send date. The customer gets what the bank wants to sell, when the bank decided.

We turn that around. For each customer, Moments detects the life moment they are in, and decides **one** useful thing, on the right channel, with an explanation.

Emma and Sofia have both just had a baby. Emma gets a family insurance review in her app. Sofia, whose budget is under pressure, gets **no offer**: a budget plan and a person, and she books a video call in two taps. Same signal, opposite decision.

Lucas never opens the app, and his rent will put him in overdraft: a push notification. Marcel, 78, is being scammed: the bank calls him, pauses the transfer, and a fraud specialist takes over. Thomas needs nothing: we leave him alone.

Technically, the LLM never decides. The decision is deterministic and auditable, 30,000 customers per second on one core. The LLM only writes, and its texts are reused per segment. That is what makes personalisation possible for 2.3 million customers, GDPR-compliant, for a few hundred dollars a month.

## Likely jury questions

**"It's just rules — where is the AI?"**
That's a choice. Rules are the guardrails and the explanation; learning (bandit, efficiency) tunes what can be tuned; the LLM writes. In production, `life_event` and `financial_stress` would become trained models, and the rules would stay as the safety layer. We don't want an opaque model deciding to sell to someone in difficulty.

**"How does it scale to 2.3 M customers?"**
Decision: measured, about 75 s for 2.3 M on one core, and it parallelises. Writing: only for customers with an action, cached per segment. The calculator is in the advisor console.

**"How do you choose the channel?"**
It's part of the decision: sensitive topic → a person; low-digital customer → voice; active in the app → card; urgent and inactive → push. Then a frequency cap and quiet hours. See `docs/CHANNELS.md`.

**"What about privacy?"**
Consent per family (a switched-off family isn't computed), art. 9 categories excluded before any computation, an LLM that receives no customer data, pseudonymised feedback, credit always validated by a person.

**"Won't customers find it intrusive?"**
That's why there's the "why" panel, "Don't show again" (permanent), one proactive message per week at most, quiet hours, and abstention by default.

**"How does the human in the loop actually work?"**
Typed tasks (outreach, callback, appointment, credit review, fraud review), each with only the actions that make sense, a mandatory note for important decisions, and a full audit trail. Bookings from the app land directly in the advisor's agenda.

**"How do you stop optimisation drifting into clickbait?"**
We optimise the completed useful action (+1.0), not the click (+0.3). Learning weighs at most 30% and never crosses a guardrail. A fairness table alerts when an age band gets more commercial pressure.

**"What about security?"**
Aikido flagged a Host header injection in our Starlette dependency. We pinned the patched version, added a Host allow-list and made sure no security logic reads the reconstructed URL — all tested. IDOR is prevented by design: identity only ever comes from the token.

**"What isn't finished?"**
Synthetic data, uncalibrated weights, simulated feedback, channels drawn rather than sent, no integration with KBC systems. It's all in the README.

**"Why KBC in particular?"**
A bank-insurer sees both sides of a life moment: money and protection. A baby is savings and insurance. One engine, one catalogue, every channel — including the Kate assistant and branch advisors.
