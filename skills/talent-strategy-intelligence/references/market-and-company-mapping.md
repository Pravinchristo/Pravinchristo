# Market research & target company mapping playbook

## Market research: what to search for

Run these as web searches (current year in the query helps freshness):

| Question | Searches that work |
|---|---|
| Comp band | `<title> salary <city> <year>`; Glassdoor, AmbitionBox (India), Levels.fyi (tech), Payscale, Indeed salary pages; government wage data (BLS OES for US) |
| Demand | `<title> jobs <city>` on job boards; count of open roles; "hiring" news for T1 companies |
| Supply | LinkedIn talent insights if the user has it; else reason from: # of companies using the stack × typical team size; university/bootcamp output |
| Movement signals | `<company> layoffs <year>`, `<company> restructuring`, `<company> acquired`, `<company> hiring freeze`, layoffs.fyi, news on GCC openings/closures |
| Who else is hiring | the same title search on job boards → which employers repeat |

Rules:
- Every number gets a source URL or the label `estimate` plus a one-line rationale.
- Prefer data from the last 12 months; say when data is older.
- Comp: report a band (P25–P75 when available), currency, and basis (base vs CTC vs total comp). Different sources disagree; say so and give your reconciled band.

## Difficulty score (1–10)

Start at 5 and adjust:
- +1 for each must-have skill rated scarcity `high`
- +1 if the location pool is small or relocation is required
- +1 if comp is below the market P50
- +1 if the combination is rare (domain + stack + leadership)
- −1 for a large talent-factory presence in the location
- −1 for remote-friendly roles or recent layoffs in T1/T2 companies (more supply)
Clamp to 1–10, and explain the main drivers in `difficulty_reason`.

Time-to-fill heuristic: difficulty 1–3 → 20–30 days, 4–6 → 35–50, 7–8 → 55–75, 9–10 → 90+.

## Building the company map

Work outward from the role:

1. **Direct competitors / same product category**: people do the identical job. Highest yield, highest resistance (retention, counter-offers).
2. **Same stack, different industry**: e.g., Python SDETs at a logistics unicorn for a fintech role. Usually underrated, and gives good candidates fewer competing offers.
3. **Talent factories**: services firms (TCS, Infosys, Cognizant, Accenture, Thoughtworks, specialist QE firms), Big-4 consulting, large GCCs. Big pools; screen harder for depth. Good for people who want a "product move".
4. **Customers and vendors of the tool stack**: companies that publish case studies with the key tools (search `"<tool>" case study`), or whose engineers blog or speak about them.
5. **Movement signals (T3)**: layoffs, reorgs, acquisitions (post-acquisition attrition peaks at 6–18 months), leadership departures, office shutdowns, stalled funding. Say what the signal is and when it happened.
6. **Startups**: Series A–C companies in the space. Good for scrappy, broad people; flag equity-vs-cash expectations.

For each company, write the **titles they use internally**. For example: Amazon "SDE-T"/"QAE", Google "SETI"/"Test Engineer", Microsoft "SDET" (legacy) → "Software Engineer", Indian services firms "Technical Lead"/"Senior Associate"/"Consultant".

## Exclusions: check before listing

- The hiring company itself, and its parent and subsidiaries.
- Clients and partners of the hiring company (poaching from them can damage relationships). If unknown, ask once or add a note: "confirm no non-solicit with X".
- Companies the user has said are off-limits.

## Pool sizing (rough, but reasoned)

Use `# companies × relevant headcount × % with the skill`, or LinkedIn result counts if the user shares them. Give a range, not a single number. Label the method in `est_size` notes or the pool description.
