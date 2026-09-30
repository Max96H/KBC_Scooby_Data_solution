# Video script (under 3 minutes)

**Setup:** `python -m data.generate && python -m scripts.simulate_feedback`, server running, browser at 1440 px, zoom 100%, language **EN**. Record screen + microphone. Keep a second tab on the advisor console.

**Tip:** regenerate the data right before recording (Marcel's pause lasts 10 real minutes, and bookings persist).

| Time | Screen | Voice-over |
| --- | --- | --- |
| **0:00 – 0:15** | Sign-in page, "Moments" | "Today a bank talks to its customers through campaigns. We propose something else: for each of KBC's 2.3 million customers, detect the life moment, decide one useful action, deliver it on the right channel — and sometimes decide to do nothing." |
| **0:15 – 0:35** | **Emma** → card "A new family member?" → behind the scenes: baby signal 0.95, score, channel "app card" | "Emma is buying baby items and started a family insurance simulation. The engine detects the moment and suggests one thing. She uses the app daily, so it's a card on her home screen." |
| **0:35 – 1:00** | **Sofia** → advisor card and booking panel → pick Friday 10:00, video → confirm. Behind the scenes: insurance **blocked**, "stress ≥ 2: no sales" | "Sofia lives the same moment, but her budget is under pressure. Same signal, opposite decision: no offer, a budget plan and a person. She books a video call in two taps." |
| **1:00 – 1:15** | **Lucas** → lock screen with notification → tap → app card "likely overdraft" | "Lucas hasn't opened the app in three weeks, and his rent will push him into overdraft on Saturday. Urgent and inactive: a push notification." |
| **1:15 – 1:40** | **Marcel** → incoming call → Accept → voice plays, transfer on hold with countdown → "I know this beneficiary" → refused | "Marcel, 78, is sending €4,900 to a stranger. He doesn't use apps, so the bank calls him. The transfer is paused for ten minutes, and the pause is enforced on the server." |
| **1:40 – 1:50** | **Thomas** → "Nothing for you today" | "And most of the time? Nothing. Thomas doesn't need anything, so we don't disturb him — and we tell him." |
| **1:50 – 2:05** | Switch **FR** then **NL** on Emma → back to **EN** → "Why am I seeing this?" → **My data**, switch off app usage | "Every message says why it exists, in the customer's language. Switch off a data family and it's no longer computed. Health and beliefs are excluded before any computation." |
| **2:05 – 2:35** | **Advisor console**: Marcel's urgent fraud review → note → "Block the transfer"; Sofia's appointment in the agenda; learning table, channel mix, cost calculator | "The engine proposes, a person decides. Each task comes with the actions that fit it — block or release a transfer, complete a meeting — and a full history. Deciding is deterministic: 30,000 customers per second on one core. The LLM only writes for customers with an action, and its texts are reused per segment: a few hundred dollars a month for 2.3 million customers." |
| **2:35 – 2:55** | README, green tests, Aikido before/after screenshots | "The LLM shapes, it never decides. 68 tests cover the engine and security, and both Aikido findings are fixed. Moments: the right gesture, at the right moment — and the courage to do nothing." |

**Before sending:** duration under 3:00, audio clear, no API key or password visible on screen.
