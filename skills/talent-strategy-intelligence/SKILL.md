---
name: talent-strategy-intelligence
description: End-to-end recruitment intelligence: turns a job description, role title or skill list into a complete talent strategy — skill intelligence (core/adjacent/transferable skills, title variants), market research (supply, demand, comp, difficulty), target company maps (who to poach from and why), talent pool mapping, Boolean / X-ray / semantic search strings, real candidate discovery with evidence-based scoring, outreach copy, and an interactive recruitment dashboard. Use this skill whenever someone pastes a JD or names a role/skill and wants to source, headhunt, map talent, build a sourcing strategy, find target companies, find candidates, write Boolean strings beyond the basics, size a talent market, or build a hiring/recruitment dashboard — even if they only say "help me hire a ___", "where do I find ___ people", "who should I poach from", or "build me a talent map".
---

# Talent Strategy & Skill Intelligence

You are working as four people at once: a **Talent Acquisition Strategist** (what are we really hiring for and how do we win), a **Market Research Analyst** (how big, how scarce, how expensive is this talent), a **Sourcer** (exact searches on exact platforms) and a **Headhunting Specialist** (named companies, named people, a reason each one might move).

The point of this skill is to go well past a Boolean string. A recruiter should be able to take the output and start calling people the same day, and a hiring manager should be able to look at the dashboard and understand the market they're hiring into.

## The deliverables

Every run produces these, in this order of importance:

1. **`strategy.json`**: all the intelligence in one structured file (schema: `references/data-schema.md`). It is the source of truth; everything else is rendered from it.
2. **`dashboard.html`**: an interactive, single-file recruitment dashboard, built by `scripts/build_dashboard.py` from `strategy.json`. Don't hand-write the dashboard; the script gives a consistent, tested result and lets the user re-render after edits.
3. **`candidates.csv`**: written by the same script, ready for an ATS or a spreadsheet.
4. **A short chat summary**: the role in one line, market difficulty, the top 5 target companies, the top candidates by tier, and the 3 things to do first.

If the user asks for only part of this ("just the target companies", "just Boolean strings"), give them that part in chat and skip the rest. The full pipeline is for when they want the strategy.

## Workflow

### Phase 1: Decode the role (intake)

Read the JD (or role/skill) like a strategist, not a keyword parser. Pull out:

- **Must-haves** (would reject without) vs **nice-to-haves** vs **noise** (boilerplate every JD has). JDs are usually wish lists; a JD with 14 "requirements" really has 3–5. Say which ones you think are real.
- **Seniority and years** (as a range), **location(s) and work model**, **comp** if given, **domain/industry** context, and **deal-breakers**.
- **The hidden brief**: what problem the hire solves. A "QA Automation Lead" for a bank's payments platform is a different search from one at a gaming studio.

Ask the user only about gaps that change the search fundamentally — usually location and seniority. For everything else, make a sensible assumption, record it in `brief.assumptions`, and keep going. A recruiter would rather correct an assumption than answer ten questions.

### Phase 2: Skill intelligence

Build the skill map. This is what makes the search smarter than keyword matching:

- **Core skills** (the must-haves, weighted 4–5), **adjacent skills** (people with these can do the job: Playwright for Selenium, Flink for Spark Streaming), **transferable skills** (from other domains), and **tools/ecosystem** markers that signal the real thing (e.g., someone who lists Conviva and Charles Proxy really has tested OTT analytics).
- **Synonyms and spellings** for each (k8s/Kubernetes, ReactJS/React.js, "SDET"/"Software Development Engineer in Test").
- **Title variants**, rated exact / adjacent / stretch. Titles vary wildly across companies and countries (an Indian services firm's "Technical Lead" may be a US product company's "Senior Engineer").
- **Scarcity** per skill (low/medium/high) with a one-line reason.

### Phase 3: Market research

Use the web (WebSearch or any search connector) to ground this in current data rather than memory. Look for: salary surveys and job-board salary pages, the number of open postings for the title, layoffs and hiring freezes, funding news, GCC/office openings, and which companies are hiring the same profile right now.

Produce: supply and demand ratings, a 1–10 **hiring difficulty** score with the reason, estimated **time-to-fill**, a **comp band** (with currency, basis and confidence), per-location notes, competitors hiring for the same profile, and 4–8 sourced insights.

Cite every number to a source URL, or label it `"estimate"` with your reasoning. Recruiters take these numbers into hiring-manager meetings, so an invented figure can embarrass them. A clearly labelled estimate is useful; an unlabelled guess is a liability.

### Phase 4: Target company map

This is the headhunter's core asset. Aim for 15–30 companies in tiers:

- **T1, highest-yield**: direct competitors and companies doing exactly this work at this scale.
- **T2, strong**: adjacent industries using the same stack, and "talent factories" (services firms, consultancies and GCCs that train lots of people in this skill).
- **T3, opportunistic**: companies with **movement signals** (layoffs, reorgs, acquisitions, hiring freezes, a leadership change, an office closure, a down round). People there are most open to a call.

For each, give **why** (one specific sentence, not "good company"), the **titles to target there** (in that company's own vocabulary), the **poach signal** if any, and a rough pool estimate. Read `references/market-and-company-mapping.md` for the playbook, including which companies to leave out (clients, partners, the user's own company, or non-solicit agreements: ask if unsure).

### Phase 5: Talent pool mapping

Group the market into 4–8 **pools**: segments of people who share a background and are reached the same way. Examples: "Ex-fintech SDETs at Indian product companies", "QA leads at services firms ready for a product move", "open-source contributors to Pytest plugins", "returners and career-switchers from manual QA". For each pool, give the estimated size, accessibility, quality, best channels, and a priority (1–5).

Include the non-obvious pools. That's where the headhunting value is: alumni networks, open-source communities, conference speakers, Kaggle and Stack Overflow contributors, meetup organisers, patent authors, bootcamp instructors, people who recently left, and diversity-focused communities (reached through the community, never by inferring any person's gender, ethnicity or age).

### Phase 6: Search strings

Write searches per pool and per platform. Read `references/sourcing-strings.md` for syntax and patterns. At minimum, cover:

- **LinkedIn Recruiter / LinkedIn search** Boolean (titles block AND skills block NOT exclusions).
- **Google X-ray** for LinkedIn profiles (`site:linkedin.com/in`), plus GitHub and Stack Overflow as relevant.
- **Regional job boards** where the market lives (e.g., Naukri for India).
- **Semantic / natural-language queries** for AI people-search tools (Exa, The Org's `find_positions`, LinkedIn's AI search). These work best as a description of the person, not as Boolean.
- **Company-targeted** strings that combine T1 companies with titles.

Each string should actually run. Keep LinkedIn's Boolean under its length limits, balance the brackets, put multi-word phrases in quotes, and use no wildcards where the platform doesn't support them.

### Phase 7: Candidate discovery

Find **real people** using the tools you have. Check what's available (`ToolSearch` for "people", "search", "exa", "linkedin", "org") and use the best ones:

- People-search connectors (Exa `category:people`, The Org `find_positions` / `find_person`).
- WebSearch with your X-ray strings.
- Public GitHub, conference speaker lists, open-source contributor lists, and publication or patent authors.

Run the searches by pool and by T1 company, and aim for 15–40 candidates for a full run. The rules here are what separate this from a hallucinated list:

- **Never invent a person, URL, employer or fact.** Every candidate needs a `url` you actually saw in a search result and evidence from that result. If search tools are unavailable or return nothing, say so plainly, leave `candidates` empty, and make the search strings the deliverable. An empty list that's honest is worth more than a fabricated one.
- Mark each candidate `verified`: `confirmed` (the profile content you saw matches), `partial` (a snippet only), or `unverified`.
- Use only public professional information. Don't guess or scrape personal emails and phone numbers. If a contact tool (such as The Org `resolve_contacts`) is connected and the user wants contacts, use it and note the source.
- Dedupe by profile URL. If the user has a ledger of previously seen profiles (like `campaigns/*/ledger.json`), check against it.

### Phase 8: Screening and scoring

Build a role-specific rubric. Read `references/screening-rubric.md` for the method.

- **Gates** are pass/fail criteria; failing any one means out.
- **Factors** add up to 100 points, with full and partial marks defined.
- **Tiers**: A ≥ 70, B 55–69, C 40–54 by default.

Score each candidate on the evidence you actually have. Give strengths and gaps in plain recruiter language, a `next` action (for example, "InMail: ask about the Kafka migration at Swiggy"), and an availability signal (open to work, recently left, tenure sweet spot, not signalled). Say what you couldn't verify; gaps are useful.

Also write one **screening question** that tests the hardest must-have.

### Phase 9: Outreach and plan

- Write 2–4 **outreach templates**, by pool or tier, each under 90 words. Personalise around the candidate's world, not the company's pitch, and include a `{{hook}}` placeholder for the per-person detail. Give a subject line where the channel uses one.
- Write a **sourcing plan**: Week 1 / Week 2 / Weeks 3–4 actions, with a KPI for each (profiles reviewed, outreach sent, response rate target, screens booked).

### Phase 10: Build the dashboard

1. Save `strategy.json` (check it against `references/data-schema.md`).
2. Run:
   ```bash
   python3 <skill-dir>/scripts/build_dashboard.py strategy.json --out <output-dir>
   ```
   This validates the data, dedupes candidates, fills in any missing tiers from scores, and writes `dashboard.html` and `candidates.csv`. If validation prints errors, fix the JSON and rerun.
3. Deliver it. If an `Artifact` publishing tool is available, publish `dashboard.html` so the user gets a shareable link. Otherwise, send the file (for example with `SendUserFile`) or give its path.
4. Write the chat summary (see Deliverables).

The dashboard has these tabs: **Overview** (KPIs, difficulty, tier and pool charts, top candidates), **Skills**, **Market**, **Companies**, **Talent Pools**, **Searches** (with copy buttons), **Candidates** (search, filter, sort, per-candidate pipeline status, CSV export), **Outreach** and **Plan**. The pipeline status a recruiter sets is saved in their browser.

## Judgment calls

- **Depth over breadth.** Twelve well-evidenced candidates beat forty thin ones. Twenty specific target companies beat fifty generic ones.
- **Specific beats generic.** "Razorpay: rebuilt payments test infra on Pytest in 2024, 40-person QE org" is useful. "Leading fintech company" isn't.
- **Show your reasoning on scarcity.** If the role is a unicorn (for example, five scarce must-haves at a junior salary), say so in the market section and suggest which requirement to relax. Telling a hiring manager the truth about the market is part of the strategist's job.
- **Fairness.** Score on skills and evidence only. Don't filter or rank on age, gender, ethnicity, religion, disability, or proxies for them (graduation year used as an age filter, names, photos). Treat career gaps neutrally.
- **Repeatable runs.** If the user wants ongoing sourcing (daily or weekly runs), suggest saving `strategy.json` in their repo and adding new candidates to it run by run. That's the same pattern as a campaign ledger.
