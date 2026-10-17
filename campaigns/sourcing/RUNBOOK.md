# Sourcing campaign: Client Partner / GCC Sales / Global Sales (IGS)

**Targets:** Client Partner, GCC Sales Manager, Global Sales Manager (plus Account Director, BD Director) · Bengaluru, Pune, Chennai · ideally 8–15 years · selling QE / testing / digital engineering services, with new-logo hunting.

**Cadence:** every 2 hours. Each run hunts the next 4 companies in `targets.json` (35 companies in tiers: QE specialists first, then digital engineering, large IT services and GCC enablers). After all 35, the rotation starts over with new query angles.

**No repeats:** `ledger.json` holds every profile URL ever delivered or screened out. A profile already in the ledger is never delivered again.

## Steps for each run
1. `git pull origin claude/inspiring-brown-3lh8cn`, then `cd campaigns/sourcing && python3 engine.py next` to get the run number and 4 companies.
2. For each company, search with the Exa connector (`web_search_exa`, numResults 10), using:
   query `category:people Client Partner or Account Director or global sales manager at <Company>, based in Bangalore, Pune or Chennai`.
   objective: profiles of current or former <Company> sales people in those cities, 8–15 years, selling QE/testing/digital services and winning new logos; exclude recruiters and job posts.
   Add one cross-company query per run (GCC sales / QE hunters in those cities). On a second pass through the rotation, vary the angles: ex-employees, "new logo", "President's Club", US-market hunters.
3. `python3 engine.py seen <urls...>` and drop anything marked SEEN.
4. Screen like a recruiter:
   - Keep only people in Bengaluru, Pune or Chennai (an unknown city may be kept, flagged).
   - Keep only sales-side roles (client partner, sales, BD, account director). Drop delivery, presales-only, marketing, HR and staffing.
   - Score 0–100: target role and QE fit, hunting evidence, years in range, GCC or global markets, and time in current role (under 9 months = less likely to move; 2–6 years = good time to approach).
   - Tiers: A ≥ 70, B 50–69, C 30–49. Write gaps honestly.
5. Write `runs/run-NNN.json` with `profiles` (kept) and `skipped` (screened-out URLs), then `python3 engine.py record NNN runs/run-NNN.json`.
6. Push `reports/run-NNN.app.json` into Sourcing Bench (https://claude.ai/artifact/EHvv6sG2RMJUfAj68hEMGn) with an ArtifactData batch `set` on `candidates`. Never overwrite a document that already exists.
7. Commit and push `campaigns/sourcing`.
8. Send Pravin the run's list: a table of new profiles by tier, with links, why and watch-outs, plus one line on where the next run goes.
