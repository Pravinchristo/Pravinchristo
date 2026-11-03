# Building a role-specific screening rubric

A good rubric makes scores comparable across candidates and across recruiters, and makes the "why" auditable.

## 1. Gates (pass/fail)

Use 2–5 gates, derived only from **true must-haves** and hard constraints:
- Core capability ("writes automation code in Python, not just record/playback")
- Location/work authorisation (if non-negotiable)
- Function ("hunter, not account farmer"; "IC, not people manager" if that matters)
- Domain only if it's genuinely required

A gate that can't be checked from a profile goes into `gaps` as "verify", and the candidate is not failed for it.

## 2. Factors (sum = 100)

Use 5–7 factors, weighted to match the hidden brief:

| Typical factor | Weight range | Full marks | Partial |
|---|---|---|---|
| Core skill depth | 25–35 | Built/owned the thing | Used it: ~60% of points |
| Domain/context fit | 10–25 | Same domain & scale | Adjacent domain: ~60% |
| Evidence of impact | 10–20 | Numbers, named outcomes | Claims without numbers: ~60% |
| Seniority fit | 5–15 | Years and scope in range | Slightly outside: ~40% |
| Stack breadth (nice-to-haves) | 5–15 | 3+ nice-to-haves | 1–2: ~50% |
| Location / availability | 5–10 | Priority location, open to work | Relocation needed: ~40% |
| Move likelihood | 0–10 | 2–5 yrs tenure, movement signal at employer | <9 months in role: ~20% |

Write `full` and `partial` text for each factor so another recruiter would score the same way.

## 3. Tiers

Default: **A ≥ 70** (call now), **B 55–69** (strong, nurture or call after A), **C 40–54** (backup / verify gaps), below 40 = out. Failing any gate = out, whatever the score.

## 4. Scoring practice

- Score only on evidence you saw. Unknown ≠ zero: give partial credit and note "verify" in gaps.
- Strengths: 2–3 specific, evidence-based phrases ("Built Pytest framework for 400 microservices at Swiggy").
- Gaps: honest and actionable ("No leadership shown: ask about mentoring").
- `next`: a concrete action plus the hook to use.
- Never use protected characteristics or their proxies.

## 5. Screening question

One open question that a real expert answers easily and a keyword-stuffer can't, aimed at the hardest must-have. Example: "Walk me through the fixture design of the last framework you built: what did you share at session scope, and why?"

## Gray areas

List ambiguous profiles patterns and your ruling (IN / GRAY / OUT) in the rubric notes or brief assumptions, e.g., "Selenium-Java SDETs with some Python scripting: GRAY, score core depth partial".
