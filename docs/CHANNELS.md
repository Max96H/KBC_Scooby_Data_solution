# Channels

The channel is a **decision of the engine**, taken right after the action. It is computed in two steps, and the phone screen in the demo changes completely depending on the result.

## Step 1: which channel suits this customer? (`channel_pref`, `engine/signals.py`)

| Situation | Preference |
| --- | --- |
| Low-digital customer who opened the app fewer than 2 times in 7 days | `voice` |
| Customer active in the app (≥ 2 openings in 7 days) or very digital | `app` |
| Everybody else | `push` |

## Step 2: which channel for this action? (`choose_channel`, `engine/decision.py`)

The first matching rule wins:

| # | Rule | Channel | Reason code |
| --- | --- | --- | --- |
| 1 | The action is a sensitive topic (stress, income loss, crypto verification) | **Advisor** | `sensitive_topic` |
| 2 | The customer prefers voice | **Voice call** | `low_digital` |
| 3 | The customer is active in the app | **App card** | `app_active` |
| 4 | The action is urgent (≥ 0.7) and the customer is inactive | **Push notification** | `urgent_inactive` |
| 5 | Otherwise | App card at the next opening | `next_app_open` |

Then two guardrails can move a push or a call back to the app:

- **Frequency cap**: at most one proactive message per 7 days (`frequency_cap`).
- **Quiet hours**: nothing between 9 pm and 8 am (`quiet_hours`), except fraud protection (`quiet_hours_overridden_for_protection`).

The *sensitivity* and *urgency* of each action are in `engine/catalog.py`.

## What the customer sees

The server returns a `delivery` object with the screen (`{"channel", "title", "text"}`); the front end draws a different phone for each channel.

| Channel | Phone screen | Then |
| --- | --- | --- |
| **App card** | Home screen with balance, the message card, buttons, "why am I seeing this", feedback | – |
| **Push notification** | Lock screen with time, date and a notification (short push text, max 110 characters) | Tapping it opens the app on the card, with "Opened from a notification" |
| **Voice call** | Incoming call screen (Accept / Decline) | *Accept*: the message is played (ElevenLabs, or the browser's voice), with a transcript and large, simple buttons. *Decline*: lock screen with a "missed call · voice message" notification |
| **Advisor** | Home screen with an advisor card and a booking panel (phone / video / branch, time slots) | Once booked, a confirmation card with a cancel button; the task appears in the advisor console |

For Marcel (voice + fraud), the transfer on hold and its countdown are shown inside the call screen.

## The personas, one per channel

| Customer | Why this channel |
| --- | --- |
| Emma, Yasmine, Nina | Active in the app → app card |
| Lucas | Medium digital, no app opening in 20 days, urgent overdraft alert → push |
| Jan & Monique, Marcel | Low digital → voice |
| Sofia | Sensitive topic (financial stress) → advisor, even though she would be reachable by push |
| Thomas | Abstention → calm "nothing for you today" card in the app |

## Where to see it in the demo

1. The chip above the phone: "Channel: …".
2. **Behind the scenes, step 1**: "Preferred channel".
3. **Behind the scenes, step 4**: the channel and the reason code in plain words; guardrails that changed it appear in step 3.
4. **↺ Replay delivery** replays the channel experience (notification, ringing call…).

## Limits

- Push notifications and calls are **drawn** on the phone mock-up, not sent. Only the voice itself is real.
- In production, voice would go through a telephony provider or the bank's assistant (Kate), and push through the app's notification service.
