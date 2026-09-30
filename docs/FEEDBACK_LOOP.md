# The learning loop

Code: `app/engine/feedback.py`, simulation: `scripts/simulate_feedback.py`, visualisation: advisor console.

```
Action sent → Customer reaction → Efficiency of the action (per segment) → Score adjustment → Better next message
```

## What is recorded (`action_events`)

One row per decision sent: **pseudonymised** customer id, action, segment (age band × household), channel, tone variant, sent time, reaction, reaction time, whether the "why" panel was opened. No transaction data.

## Reactions and weights

| Reaction | Weight | Set by |
| --- | --- | --- |
| Ignored | 0 | server (default) |
| Seen | +0.1 | server, on display |
| Click / "Useful" | +0.3 | customer |
| **Useful action completed** (review done, appointment booked, transfer cancelled, meeting held…) | **+1.0** | **server only**, when the action actually happens (including advisor outcomes) |
| "Not now" | −0.5 | customer → 30-day pause |
| "Don't show again" | −1.0 | customer → permanent suppression |
| Reported as intrusive | −1.5 | customer → permanent suppression |

Rules: the strongest reaction is kept, and **a refusal can never be erased** by a positive reaction. The customer cannot report "completed" themselves (test: `test_client_cannot_self_report_completed`).

## Efficiency

```
efficiency(action, segment) = mean weight over 30 days, rescaled to [0, 1]
score_final = score_base × (0.7 + 0.3 × efficiency)
```

The influence is capped at 30%: learning cannot push an action past a guardrail, and a blocked action stays blocked whatever its score.

## Explore or exploit: Thompson sampling

For each action × segment, each tone variant (`warm`, `direct`) has a Beta(1 + successes, 1 + failures) distribution. For each new decision we draw from each distribution and keep the best draw. Good variants naturally get more traffic, and the others keep being tested while there is uncertainty.

In the simulation, the hidden effect is: warm tone works better for happy moments (baby, grandchild), direct tone works better for protection (scam, overdraft). The advisor console shows the bandit discovering it. Test: `test_thompson_prefers_better_variant`.

**What is optimised:** tone (and, in production: wording, channel, timing). **What is never optimised:** sending an offer to a customer under financial stress, or overriding a refusal.

## Guardrails of the learning

1. **We optimise value, not clicks**: +1.0 for a completed useful action, +0.3 for a click.
2. **Ethical rules beat scores.**
3. **A refusal is information, not an obstacle**: frequency goes down, never up.
4. **Fairness**: the console compares the share of commercial actions and the refusal rate per age band, and raises an alert when a band receives more than 1.5× the average commercial pressure. In the simulation, the alert fires for the 26-44 and 45-64 bands: exactly what this table is meant to reveal.
5. **Minimal data**: reaction + pseudonym, nothing else.

## Honestly

The demo feedback is **simulated**: 400 synthetic customers over 30 days, with reaction probabilities set in `scripts/simulate_feedback.py` and a channel mix that roughly mirrors the engine's rules. There is no learning in production.
