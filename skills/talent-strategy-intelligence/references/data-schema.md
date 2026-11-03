# strategy.json schema

One JSON object. `build_dashboard.py` validates required keys and types, and it tolerates extra keys. Arrays may be empty, but keep the keys. Fields marked *req* are required.

```jsonc
{
  "meta": {
    "role": "Senior QA Automation Engineer (Python)",    // req
    "client": "IGS",                                       // hiring company, if known
    "generated": "2026-11-03",                             // req, ISO date
    "prepared_by": "Talent Strategy & Skill Intelligence",
    "input_summary": "JD pasted by user, 3–5 yrs, Chennai/Bengaluru hybrid"
  },
  "brief": {
    "summary": "One-paragraph hidden brief: what problem this hire solves",   // req
    "seniority": "Senior IC",
    "years": [3, 6],
    "locations": ["Chennai", "Bengaluru"],
    "work_model": "Hybrid (3 days)",
    "must": ["Python test automation with Pytest", "API testing"],            // req
    "nice": ["Playwright", "Performance testing"],
    "dealbreakers": ["Manual-only testing"],
    "assumptions": ["Comp not given; assumed market median"]
  },
  "skills": [                                  // req
    {"name": "Pytest", "category": "core",     // core | adjacent | transferable | tool
     "weight": 5,                              // 1–5
     "scarcity": "medium",                     // low | medium | high
     "synonyms": ["py.test", "pytest-bdd"],
     "why": "Framework the team standardises on"}
  ],
  "titles": [{"title": "SDET", "fit": "exact"}],   // exact | adjacent | stretch
  "market": {                                  // req
    "supply": "medium", "demand": "high",      // low | medium | high
    "difficulty": 6,                           // 1–10
    "difficulty_reason": "Python+API automation common; leadership + fintech rare",
    "time_to_fill_days": 45,
    "comp": {"currency": "INR", "low": 1800000, "high": 3000000, "basis": "annual CTC",
             "confidence": "medium", "source": "https://… or 'estimate: reasoning'"},
    "insights": [{"text": "…", "source": "https://…"}],   // source may be "estimate"
    "competitors_hiring": ["Freshworks", "Zoho"],
    "geo": [{"location": "Chennai", "supply": "high", "comp_note": "~10% below Bengaluru", "priority": 1}]
  },
  "companies": [                               // req
    {"name": "Freshworks", "tier": "T1",       // T1 | T2 | T3
     "type": "direct competitor",              // direct competitor | adjacent | talent factory | movement signal | GCC | startup
     "why": "SaaS QE org in Chennai standardised on Python/Pytest",
     "titles_to_target": ["Senior SDET", "Lead QA Engineer"],
     "poach_signal": "Reorg of QE under platform team, 2026",   // "" if none
     "est_pool": "60–100",
     "url": "https://…"}
  ],
  "pools": [                                   // req
    {"name": "Product-company SDETs, Chennai", "description": "…",
     "est_size": "800–1,200", "accessibility": "medium",   // low | medium | high
     "quality": "high", "channels": ["LinkedIn Recruiter", "Naukri"], "priority": 1}  // 1 = highest
  ],
  "channels": [{"name": "Chennai Python meetup", "why": "…", "tactic": "Sponsor a talk; speaker list"}],
  "searches": [                                // req
    {"platform": "LinkedIn Recruiter",         // free text; also "Google X-ray", "GitHub", "Naukri", "Exa (semantic)" …
     "label": "Core SDET, T1 companies",
     "pool": "Product-company SDETs, Chennai",
     "query": "(\"SDET\" OR \"QA Automation\") AND (Python AND Pytest) …",
     "notes": "Add location filter Chennai + 50 mi"}
  ],
  "rubric": {                                  // req
    "gates": [{"id": "G1", "text": "Writes automation code in Python (not only record/playback)"}],
    "factors": [{"name": "Python automation depth", "points": 30,
                 "full": "Built/owns a Pytest framework", "partial": "Uses existing framework: 18"}],
    "tiers": {"A": 70, "B": 55, "C": 40},
    "screen_question": "Walk me through a test framework you built…"
  },
  "candidates": [                              // req (may be empty, with the reason in meta.input_summary)
    {"name": "…", "url": "https://linkedin.com/in/…",   // req: a URL actually seen
     "headline": "…", "company": "…", "location": "…", "years": 5,
     "pool": "Product-company SDETs, Chennai", "source": "Exa people search: T1 Freshworks",
     "score": 78, "tier": "A",                 // tier optional: derived from score + rubric.tiers
     "gates_passed": true,
     "skills": ["Pytest", "Playwright"],
     "strengths": ["…"], "gaps": ["…"],
     "avail": "Open to work",                  // Open to work | Recently left | Tenure sweet spot | Not signalled
     "verified": "partial",                    // confirmed | partial | unverified
     "next": "InMail: ask about …"}
  ],
  "outreach": [{"audience": "Tier A, product SDETs", "channel": "LinkedIn InMail",
                "subject": "…", "message": "Hi {{first_name}}, {{hook}} …"}],
  "plan": [{"phase": "Week 1", "actions": ["…"], "kpi": "150 profiles reviewed, 40 InMails"}]
}
```

Notes:
- Keep comp numbers as plain numbers (no separators) so the dashboard can format them.
- `score` is 0–100. A candidate with `gates_passed: false` is shown as "Out", whatever the score.
- Strings may contain any characters; the build script escapes them safely.
