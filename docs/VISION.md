# Vision

> The brief asks us first to imagine the ideal experience **without constraints**, then to show how to deliver it to **more than 2.3 million customers**. This document does both.

## One sentence

The bank detects the *moment* each customer is in, decides **one** right action at the right time, delivers it on the right channel, and always explains why. When nothing is useful, it says nothing.

## The ideal experience, without constraints

**Sarah, 33, Ghent. A year with her bank in 2030.**

- **March.** Sarah buys a pram and, one evening, starts a family insurance simulation she doesn't finish. The next morning her app doesn't show "our offers of the month". It asks one question: *"A new family member? Does your cover already include your child?"* Two minutes, done. Under the message, a *"Why am I seeing this?"* link shows exactly what the bank noticed, with a switch to turn that data off.
- **June.** Maternity leave, income down. The bank sees it too. This time **no offer**: a budget plan for the next six months, and an advisor who offers a call without selling anything. Sarah books a video call for Friday from the app. She never had to explain her situation.
- **September.** Her mother Monique, 67, who hardly ever opens the app, gets a short **phone call** in her own language. It explains how to save for her granddaughter and what to know about gifts, then offers a callback.
- **October.** Sarah's brother hasn't opened the app for weeks. A **notification** on his lock screen warns him that rent and energy will push his balance below zero on Thursday. One tap, a payment is moved.
- **November.** Monique's neighbour Marcel gets a call from a "bank technical service" asking him to "secure" €4,900. When he makes the transfer, his bank stops it gently: *"10-minute safety pause. Nobody from the bank will ever ask you to move your money."* A fraud specialist calls him within minutes. He cancels.
- **The rest of the year.** Most days, the bank says nothing. On purpose.

What Sarah remembers is not a product. It's that her bank **understands her situation, acts at the right moment, on the channel she actually uses, knows when to stay quiet, and never takes advantage of a hard moment**.

## The principles that follow

1. **One decision per customer and per moment**, not one campaign per segment.
2. **The same signal can lead to opposite decisions.** A new baby triggers an offer for Emma and support without sales for Sofia.
3. **Abstaining is a real action**, visible and explained.
4. **Customer value weighs more than bank value** in the score (0.35 vs 0.10).
5. **The channel is a decision too**: app card for active customers, push when urgent and the app is unused, voice for low-digital customers, a person for sensitive topics.
6. **Transparency by reflex**: every message has its "why", built by the engine, not by generative AI.
7. **The customer stays in control**: switch off a data family and it is no longer computed at all. Choose your language.
8. **People stay in the loop** for sensitive topics, fraud and any credit decision, with typed tasks and an audit trail.
9. **Generative AI shapes, it never decides.** That is what makes the whole thing auditable, compliant and affordable at scale.

## The six action families

| Family | Idea | Demo example |
| --- | --- | --- |
| Inform | Useful information, nothing sold | Yasmine: the 50/30/20 rule |
| Protect | Avoid a problem | Marcel: scam pause · Lucas: overdraft alert |
| Simplify | Do it for the customer, or in one tap | Nina: resume the simulation |
| Propose | A product fitting the moment | Emma: family insurance |
| Accompany | Put a person in the loop | Sofia: budget + advisor |
| **Abstain** | Do nothing, and say so | Thomas |

## Answers to the 5 questions of the brief

**1. Which signals help us understand what customers need?**
Four families, each subject to consent: transactions (salary, spending categories, balance, savings, late fees), digital usage (simulations started or abandoned, pages viewed, app activity), products and deadlines (end of fixed rate, renewals), profile (age, household). Fraud prevention has its own legal basis. Health, beliefs and orientation data are **excluded before any computation**. Details: [PRIVACY.md](PRIVACY.md).

**2. How can customers be recognised by situation, behaviour and intent?**
Through **derived signals** with a 0–1 confidence and readable evidence: `life_event` (baby, grandchild, first job, housing, income loss, retirement), `financial_stress` (level 0 to 3), `intent`, `scam_risk`, `overdraft_risk`, deadlines, channel preference. The engine only acts above a confidence of 0.6.

**3. How can personalised experiences adapt automatically to each customer?**
The engine chooses the action (score + guardrails), the channel and the tone (learned by a bandit). Rendering adapts language (EN/FR/NL) and wording. The phone screen itself adapts to the channel: a lock-screen notification, an incoming call, an app card, or an advisor booking panel.

**4. How can this work across products, services and channels?**
One action catalogue covers banking, insurance and services — the advantage of a bank-insurer: a life moment touches both. The channel is a *decision*, not a silo: same engine, same journal, same feedback loop, whether the message arrives in the app, as a notification, as a call or through an advisor.

**5. How can you create impact for millions of customers at once?**
Detection and decision are **deterministic**: ≈ 30,000 customers per second on one core, 2.3 M in just over a minute. Generative AI only runs for customers who trigger an action, and the text is **cached per segment × moment × language × tone**: a couple of thousand texts for the whole base. See [SCALABILITY.md](SCALABILITY.md).
