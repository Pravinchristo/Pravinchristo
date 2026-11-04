# Runbook: a Claude session operating as MARK and JOE

Use this when Pravin asks a Claude session to run a hiring campaign with MARK & JOE. All commands run from `apps/mark-joe`. The database is the source of truth; the conversation is only supporting context.

## 0. Before every campaign: connectors

1. List the tools this session actually has (ToolSearch for `people`, `org`, `linkedin`, `search`, `calendar`, `sheets`).
2. For each relevant one, make one small real call. Record the result, and only then mark it connected:
   ```bash
   python3 -m markjoe.cli connector set "The Org" connected --actions "people search by company/title,org chart" --evidence "find_positions returned N rows on YYYY-MM-DD"
   ```
   If a call fails or needs sign-in, record `not_connected` or `needs_auth` and say so to Pravin.
3. Never assume bulk sourcing. As of 2026-11-04 the tools seen in this environment were: The Org (people/role search, max 25 per call, uses credits), LinkedIn Hiring Pro (job-post preview only, **no candidate search**), GitHub (repo access scoped to this repo; user search through `gh api search/users` only), web search. Verify again each time; this list goes stale.

## 1. Intelligent Mode (MARK)

```bash
python3 -m markjoe.cli jd new path/to/jd.txt      # prints what MARK understood + the first question
```
Ask Pravin **one question at a time**, in MARK's voice, including the "why it matters" line. Record each answer:
```bash
python3 -m markjoe.cli answer REQ-XXXX "<Pravin's answer>"
python3 -m markjoe.cli ask REQ-XXXX               # next question
```
Raise any contradictions or market warnings it prints. Stop asking when `ready_for_plan` is true and Pravin wants to move on.

## 2. Channels (memory)

```bash
python3 -m markjoe.cli channels list --family <job_family>
```
Show the saved channels, ask whether to reuse them and whether to add new ones, then:
```bash
python3 -m markjoe.cli channels confirm REQ-XXXX "LinkedIn Recruiter" "Google X-Ray" "GitHub"
python3 -m markjoe.cli channels add "<custom channel>" --category Community --methodology "..."
```

**Recruiter portals.** OctoHunt (https://octohunt.com/) and SourceGo (https://sourcego.blogspot.com/) are pre-approved for every campaign. The plan gives OctoHunt the GitHub-style query and SourceGo the X-Ray strings. On 2026-11-04 neither domain resolved from the Claude cloud session (DNS failure), so a session cannot open them unless they are added to the environment's allowed network domains. Until then, hand Pravin the strings to run there, and log each run with `search log ... "OctoHunt"` / `"SourceGo"` and the evidence he gives. When you first see what a portal actually offers, record it with `channels add "OctoHunt" --methodology "..."`.

## 3. Plan, then wait for approval

```bash
python3 -m markjoe.cli plan REQ-XXXX > plan.json
```
Summarise it for Pravin: key Booleans, X-Ray strings, top companies, channel plan and warnings. **Wait for an explicit yes**, then:
```bash
python3 -m markjoe.cli approve REQ-XXXX --by "Pravin"
```

## 4. Hunt (MARK)

* Run only searches the session can really run (web search with the X-Ray strings, The Org, `gh api search/users`). Log each one with evidence:
  ```bash
  python3 -m markjoe.cli search log REQ-XXXX "Google X-Ray" --query "<string>" --results 9 --evidence "web search YYYY-MM-DD, top 10 read"
  ```
* For LinkedIn Recruiter, Naukri and other closed platforms: give Pravin the strings and ask for exports or pasted profiles. Never claim to have searched them.
* Write each real profile you found to a JSON file (one object or a list). Required: `full_name`, plus `source_url` or `linkedin_url`. Include `resume_text` when you have profile or resume text, so JOE can score. Leave out anything unknown; never guess notice periods, Open to Work or contact details.
  ```json
  {"full_name": "...", "linkedin_url": "...", "current_company": "...", "current_designation": "...",
   "location": "...", "source_channel": "Google X-Ray", "source_url": "...", "resume_text": "..."}
  ```
  ```bash
  python3 -m markjoe.cli candidate add REQ-XXXX found.json
  ```
  Duplicates come back as `"duplicate": true` and are not re-added.

## 5. Evaluate, challenge, refine (JOE + MARK)

JOE scores automatically on `candidate add`. Then:
```bash
python3 -m markjoe.cli candidate show CAN-XXXX     # breakdown, evidence, flags, challenges, screening questions
python3 -m markjoe.cli refine REQ-XXXX             # MARK's adjustments from JOE's results
```
Apply refinements by running new searches (and logging them). Repeat until the shortlist has enough clean profiles:
```bash
python3 -m markjoe.cli shortlist REQ-XXXX
```

## 6. Report to Pravin

Send the shortlist as a table: name with link, company, score and class, the strongest evidence, critical gaps or flags, and the next screening question. State which channels were actually searched and which were manual. Separate verified facts from assumptions.

Never move anyone to `submitted` or later stages yourself. If Pravin explicitly says to submit a named candidate:
```bash
python3 -m markjoe.cli status REQ-XXXX CAN-XXXX submitted --recruiter "Pravin" --note "approved in chat YYYY-MM-DD"
```

## 7. Keep the memory

Commit nothing from `var/` (candidate data stays out of git). To keep the database between cloud sessions, point `MARKJOE_DB` at storage Pravin controls, or export:
```bash
python3 -m markjoe.cli export xlsx shortlist.xlsx --req REQ-XXXX
```
