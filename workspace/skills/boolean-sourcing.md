---
name: boolean-sourcing
description: Build Boolean / X-ray search strings and sourcing plans for a role.
---

# Boolean & X-ray sourcing

1. Pull the must-have skills, nice-to-haves, seniority and location from the request or JD.
2. For each must-have, list synonyms and common spellings (e.g. "Selenium" OR "WebDriver"; "Pytest" OR "py.test").
3. Write three strings:
   - **LinkedIn Recruiter / Boolean:** (title variants) AND (must-have groups) NOT (exclusions such as "intern" or "student").
   - **Google X-ray (LinkedIn):** `site:linkedin.com/in ("QA Automation" OR "SDET") ("Python") ("Pytest" OR "Selenium") "<location>"`
   - **Google X-ray (GitHub):** `site:github.com "<location>" ("pytest" OR "selenium") followers`
4. Give 2-3 alternative title variants the market uses for the same role.
5. Output: the strings in code blocks, then a one-line tip on how to widen or narrow the search.

## Preferences learned
- (none yet; the agent fills this in from your feedback)
