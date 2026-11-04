# MARK & JOE: Intelligent Talent Acquisition Command Centre

Two recruiter agents that work as one team:

| Agent | Role | What it does |
|---|---|---|
| <img src="web/mark.svg" width="40" alt="MARK logo: crosshair locked on a person"><br>**MARK** | Senior Talent Hunter | Reads the JD, asks only what's missing (Intelligent Mode), expands skills, maps target companies, writes every Boolean / X-Ray / GitHub string, plans channels, keeps channel memory, and refines the hunt from JOE's feedback. |
| <img src="web/joe.svg" width="40" alt="JOE logo: resume under a magnifying glass with a check"><br>**JOE** | Senior Technical Recruiter | Scores each resume on a 100-point evidence model, separates keyword mentions from real project, hands-on, architecture, production and leadership evidence, flags critical gaps, duplicates and gaps, and writes the screening questions. |

MARK's logo is a round blue badge with a crosshair locked on a person (the hunt). JOE's is a rounded violet square with a resume under a magnifying glass and a check (the evaluation). Shape and symbol differ as well as colour, so the two stay distinct for colour-blind users and in print. Both are in `web/` as standalone SVGs.

The recruiter approves the plan, decides every submission and can correct any record. Every change goes to an audit trail.

## Run it

Python 3.9+ only. No packages to install.

```bash
cd apps/mark-joe
python3 -m markjoe.server            # http://127.0.0.1:8765
```

Data lives in `apps/mark-joe/var/markjoe.db` (SQLite, git-ignored). Use `--db` or `MARKJOE_DB` to put it somewhere else, for example a synced drive. Set `MARKJOE_TOKEN` to require a token on every API call (`http://127.0.0.1:8765/?token=...`).

```bash
python3 -m unittest discover -s tests     # 20 tests
```

## The workflow (enforced in code, not just in the UI)

1. **JD in.** MARK parses title, experience, location, work mode, notice, budget, domain, education, profile count, target and excluded companies, and mandatory vs preferred skills (from "Must have" / "Good to have" sections).
2. **Intelligent Mode.** MARK asks one question at a time, essentials first, then job-family follow-ups (Data Engineering, SDET, DevOps, Backend, Frontend, Data Science). Each question says why it matters. It flags contradictions (e.g. junior title with 9+ years, min > max, remote vs WFO) and market limits (too many mandatory skills, scarce skills, multi-cloud mandatory, tight notice at senior levels, budget heuristic).
   * Answers change the search. "No, EMR is fine" moves Databricks to preferred and adds its equivalents as transferable. "Yes" to "Is production Kafka mandatory?" tells JOE to require production evidence for Kafka.
3. **Channel memory.** Saved channels are shown first, with past strategies for the same job family. You pick any number of channels and can add custom ones (with a portal URL and which strings MARK should hand it: Boolean, X-Ray or GitHub-style). Nothing is deleted; channels can be deactivated.
   * **Recruiter portals, pre-selected in every campaign:** [OctoHunt](https://octohunt.com/) gets MARK's GitHub-style query (language, location, skill topics), and [SourceGo](https://sourcego.blogspot.com/) gets the Google X-Ray strings. Both are manual: you open the portal, run the string, and log the run with evidence. What each portal offers (filters, limits, terms) is recorded as "confirm on first use", because neither site could be reached to verify it when they were added.
4. **Search plan.** Broad, narrow, skill-based, designation-based, company-specific, immediate-joiner, Open to Work and alternative-skill Booleans; Google X-Ray strings (LinkedIn, Open to Work, GitHub, Stack Overflow, resume pages, speakers); a GitHub user/topic strategy; ranked target companies; a channel-by-channel plan; warnings; connector gaps.
5. **Approval gate.** Profiles can't be added until the recruiter approves the plan. Approved strings are saved to channel memory.
6. **Hunt.** Sourced profiles need a name and a source (URL, resume link or resume text). Searches count only when logged with evidence.
7. **JOE evaluates** each profile automatically, then the two agents challenge each other (see below).
8. **Refine.** MARK reads JOE's results: common skill gaps, the companies strong profiles came from, weak channels, keyword-only resumes.
9. **Final shortlist.** Shortlisted by both agents with no critical gaps, capped at the number you asked for. **Only the recruiter can move a candidate to submitted, L1, L2, offered or joined.**

## JOE's scoring model (default, configurable per requirement)

| Factor | Points | How it's earned |
|---|---|---|
| Mandatory technical skills | 35 | Credit per skill by its strongest evidence: keyword 0.2, project 0.6, hands-on 0.85, architecture / production / leadership 1.0 |
| Relevant project experience | 20 | Years in dated roles that use the required stack (60%) and share of mandatory skills used in projects (40%) |
| Hands-on implementation | 15 | Share of mandatory and preferred skills with hands-on or deeper evidence |
| Architecture & design | 10 | Design evidence tied to the required skills |
| Experience alignment | 5 | Total years from merged date ranges (overlaps are not double-counted) |
| Domain alignment | 5 | Domain named in the resume (full marks if no domain requirement) |
| Availability | 5 | Notice within limit: full if verified, 60% if only claimed |
| Location & work mode | 5 | Match, remote, or open to relocate |

85–100 high-potential shortlist · 70–84 potential shortlist · 55–69 secondary pipeline · below 55 not recommended.

* A critical mandatory skill with no evidence, or only a keyword, puts the candidate on **Hold** and is flagged, whatever the total.
* Each score line carries its evidence, and each skill keeps the resume sentences that prove it, with a confidence level.
* Age, date of birth, gender, marital status, religion, caste, nationality, passport and photo lines are removed before scoring. Employment gaps are shown as questions to ask and are never scored.
* If you answer "yes, prioritise architecture" in Intelligent Mode, architecture goes up to 15 points and hands-on drops to 10.

**Challenges between agents:** JOE challenges MARK when an immediate-joiner or Open to Work tag has no evidence. MARK challenges JOE when a score of 70 or more rests on keyword-only skills, or when a low score hides in-range relevant experience with no critical gap.

## Honesty rules built in

* The dashboard reads only stored records. An empty database shows zeros and empty states, not sample data.
* Channels and connectors start **not connected**. Marking one connected requires written evidence of a successful call.
* "Immediate joiner" and "Open to Work" count only with evidence. An unverified claim is stored as claimed and challenged.
* Duplicates are caught on normalised LinkedIn URL, GitHub URL and email. A name and company match is flagged as a possible duplicate and never merged automatically.
* Seed company stacks (`data/companies.json`) are general knowledge, marked unverified, with a research date. Candidate counts per company come from real records.
* The skill library's `market_availability` is a planning heuristic and is labelled as one.
* Contact details are not part of the dashboard payload or exports, apart from profile and resume links.
* CSV export escapes leading `= + - @` to block spreadsheet formula injection.

## Dashboard modules

Executive overview · Requirements · Campaign (Intelligent Mode chat, channel memory, connector check, search plan, add profile, JOE result, search log, refinement, shortlist) · Candidates (filters for requirement, title, skill, experience, location, company, channel, availability, notice, score and status; a detail drawer with the breakdown, evidence, screening questions, status changes, remarks, corrections, history and audit) · Channel performance · Company mapping · Skill intelligence · Funnel · Agent activity · Connectors. Export to CSV and Excel (.xlsx), with filters applied.

## Data model (SQLite)

`requirements`, `candidates` (unique `CAN-` IDs; unique normalised LinkedIn, GitHub and email), `candidate_skills`, `candidate_projects`, `pipeline`, `sourcing_channels`, `channel_memory`, `search_strategies` (versioned: proposed / approved / superseded), `search_runs`, `target_companies`, `company_talent_maps`, `resume_evaluations`, `candidate_status_history`, `recruiter_feedback`, `agent_activity`, `connector_registry`, `recruitment_analytics`, `skill_library`, `audit_log`.

## Files

```
markjoe/db.py         schema, audit trail, normalisation, seeding
markjoe/skills.py     Skill Intelligence Engine
markjoe/intake.py     MARK: JD parser and Intelligent Mode questioning
markjoe/hunt.py       MARK: Booleans, X-Ray, GitHub, company map, channel memory, plan, refinement
markjoe/evaluate.py   JOE: evidence levels, experience maths, 100-point score, duplicates, challenges
markjoe/service.py    workflow gates (approval, recruiter-only submission, evidence rules)
markjoe/analytics.py  dashboard metrics from stored records
markjoe/export.py     CSV and .xlsx export (standard library)
markjoe/server.py     local JSON API + dashboard
markjoe/cli.py        command line (used by Claude sessions running as MARK/JOE)
web/index.html        dashboard (no external libraries)
data/*.json           skill library, channel catalogue, seed companies
RUNBOOK.md            how a Claude session operates as MARK and JOE
```

## Limits to know

* JOE's evidence extraction is rule-based (verbs, sections, date ranges). It is consistent and explainable, but a recruiter should still read the evidence column. Resumes need to be pasted as text; PDF/DOCX parsing is not built in.
* MARK does not scrape LinkedIn, Naukri or other closed platforms. It writes the strings; you, or a connected tool in a Claude session, run them, and the results are logged with evidence.
