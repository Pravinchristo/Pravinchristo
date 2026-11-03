# Sourcing strings: syntax and patterns

## Structure that scales

Build every Boolean from blocks, then combine:

```
TITLES   = ("SDET" OR "QA Automation Engineer" OR "Test Automation Engineer" OR "Software Engineer in Test")
CORE     = (Python AND (Pytest OR "py.test"))
CONTEXT  = (API OR REST OR Postman OR "Requests")
EXCLUDE  = NOT (intern OR trainee OR fresher OR recruiter OR "talent acquisition")
→ TITLES AND CORE AND CONTEXT EXCLUDE
```

Write a **narrow** version (exact titles + all core skills, which gives high precision), a **broad** version (adjacent titles + any 2 core skills, which gives volume), and a **lateral** version (adjacent skills and titles from the skill map, which surfaces hidden talent).

## LinkedIn (Recruiter / Sales Navigator / basic search)

- Operators: `AND`, `OR`, `NOT` (uppercase), `"quotes"` for exact phrases, `( )` for grouping. No wildcards `*`.
- Put titles in the **Job title** field with "Current" scope when you need current role only; skills/keywords in **Keywords**.
- Basic search is limited in length (~1,000 chars incl. spaces in practice); Recruiter allows more. Keep each string compact.
- Use the company field with T1/T2 lists rather than stuffing company names into the keyword Boolean.
- Use the Spotlights/filters (Open to Work, "More likely to respond", Past company) and mention them in `notes`.

## Google X-ray

```
site:linkedin.com/in ("SDET" OR "QA Automation") ("Pytest" OR "py.test") ("Chennai" OR "Bengaluru") -jobs -hiring
site:github.com "pytest" "Chennai" (followers OR repositories)
site:stackoverflow.com/users "Chennai" pytest
site:linkedin.com/in "Freshworks" ("SDET" OR "QA") "Python"
```

- Google ignores most nesting beyond one level and caps at ~32 words. Keep it short; run several variants instead of one mega-string.
- `-jobs -hiring -recruiter` removes job posts and recruiters.
- Country subdomains (`in.linkedin.com/in`) narrow by geography.

## GitHub

- User search: `language:Python location:Chennai followers:>20`
- Code search for tool usage signals: `"pytest.fixture" path:conftest.py` (then look at the authors).
- Contributors of key OSS repos (e.g., pytest-dev plugins, Playwright-python) are a talent pool in their own right.

## Regional job boards and databases

- **Naukri Resdex** (India): keyword Boolean is supported (`AND`/`OR`/`NOT`, quotes), with separate fields for experience, CTC, notice period and location. Note notice-period filters (15/30/60/90 days).
- **Indeed Resume / Monster / Dice** (US): Boolean similar to LinkedIn; Dice is tech-focused.
- **StepStone / Xing** (DACH), **Seek** (AU/NZ), **Bayt** (Middle East), **JobStreet** (SEA).

## Semantic / AI people search

Exa (`category:people`), LinkedIn AI search, The Org `find_positions` and other natural-language tools work best with a **description** rather than Boolean:

```
Senior QA automation engineers in Chennai or Bengaluru with 3–6 years building Python/Pytest
API test frameworks at product companies; exclude recruiters and job postings.
```

For headhunting, add a company and an angle: `…current or former Freshworks or Zoho SDETs…`, `…who recently left…`, `…open to work…`.

## Diversity sourcing (lawful, community-based)

Reach under-represented talent by **where you search**, not by inferring traits: women-in-tech groups and their member or speaker lists (Women Who Code alumni, PyLadies, Women in Testing), returnship programmes, disability-inclusive job boards, veteran networks, HBCU/HSI alumni (US). Never add gendered names, photos or age proxies to a string.

## Quality checklist for every string

- [ ] Brackets balanced; quotes paired
- [ ] Operators uppercase (LinkedIn)
- [ ] Multi-word phrases quoted
- [ ] No wildcards on LinkedIn
- [ ] Exclusions remove recruiters, job posts, juniors (as appropriate)
- [ ] Synonyms from the skill map included
- [ ] Each string is tagged with the pool it targets
