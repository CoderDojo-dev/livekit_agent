# UAT Plan — FR / AR / EN (CDC section 5, cookbook section 20)

**Hard rule (Blueprint section 18 / cookbook section 20):** every CDC use case is one scenario, run in
**French, Arabic, and English** — never "English, the rest are similar". The automated suite asserts the
deterministic layers in all three (`notification-service/tests/test_multilingual.py`,
`agent-worker/tests/uat/test_multilingual.py`); the spoken scenarios below are the manual voice UAT.

| # | CDC | Scenario | FR | AR | EN |
|---|---|---|---|---|---|
| 1 | 5.1 | Invoice consultation (read-only) | ☐ | ☐ | ☐ |
| 2 | 5.2 | Balance / data consultation | ☐ | ☐ | ☐ |
| 3 | 5.3 | Payment deferral (eligible) | ☐ | ☐ | ☐ |
| 4 | 5.3 | Payment deferral refused (ineligible) | ☐ | ☐ | ☐ |
| 5 | 5.4 | Pay an invoice (within cap) | ☐ | ☐ | ☐ |
| 6 | 5.4 | Pay above cap → escalate (never execute) | ☐ | ☐ | ☐ |
| 7 | 5.5 | SIM unblock (identity-verified) | ☐ | ☐ | ☐ |
| 8 | 5.5 | SIM unblock refused (identity fails twice) | ☐ | ☐ | ☐ |
| 9 | 5.6 | Prepaid top-up | ☐ | ☐ | ☐ |
| 10 | 5.9 | Open a support ticket + written confirmation | ☐ | ☐ | ☐ |
| 11 | 6.5 | Step-up identity verification | ☐ | ☐ | ☐ |
| 12 | 7 | Escalation to a human (frustration) | ☐ | ☐ | ☐ |
| 13 | 8.1 | Recording consent — "no" path | ☐ | ☐ | ☐ |
| 14 | 13 | Turn-detection: mid-sentence pause / language switch / interruption | ☐ | ☐ | ☐ |

**Resilience (cookbook section 16), once per language:** deliberate STT / LLM / TTS primary failure each
shows graceful fallback; both-failing degrades to an audited "let me get you to a person" escalation.