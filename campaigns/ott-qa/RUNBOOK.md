# OTT Test Engineer: daily sourcing runbook

**Brief:** OTT Test Engineers with 2–6 years of experience who test streaming apps (Smart TV, Android TV, Fire TV, Roku, Apple TV, mobile, web) and validate analytics with tools such as Conviva, Mixpanel, Adobe Analytics/Heartbeat, GA4/GTM, CleverTap, Firebase, Mux, NPAW and Charles Proxy. Open-to-work candidates and immediate joiners rank first. The search covers all of India, with priority on Bengaluru, Chennai, Hyderabad, Pune, Mumbai and Noida.

**Dashboard:** OTT QA Talent Desk, https://claude.ai/artifact/NJ8JJzHJ1xRdQRTv82qWen
The dashboard has three collections:
- `candidates`: written by Claude.
- `runs`: written by Claude.
- `status`: written by viewers. Never overwrite it.

**Schedule:** daily at 09:45 IST.

## Each run
1. Run `python3 campaigns/ott-qa/engine.py next`. It returns the run number and 3 rotation targets.
2. Run Exa `category:people` searches, 8 results each:
   - one search per target;
   - plus one availability sweep (`#OpenToWork` / immediate joiner OTT tester), which runs every day;
   - plus a city sweep that rotates through Chennai, Hyderabad, Pune and Noida.
3. Check the URLs with `engine.py seen <urls>` and drop any marked SEEN.
4. Screen each profile with this rubric:

   | Signal | Points |
   |---|---|
   | OTT/video-player testing | +30 |
   | Named analytics tools | +25 |
   | 2–6 years | +15 |
   | Open to work / immediate | +15 |
   | Device breadth | +10 |
   | Priority city | +5 |

   Tiers: A ≥70, B 50–69, C 30–49. Below 30, or out of band (leads, 8+ yrs, <1 yr), goes in `skipped`.
5. Write `campaigns/ott-qa/runs/run-NNN.json`. Each profile includes `avail`, which is one of:
   - Immediate joiner
   - Open to work
   - Recently left role
   - Not signalled
   It also includes `tools[]`, `city` and `notice`.
6. Run `engine.py record N runs/run-NNN.json`. This writes `reports/run-NNN.{md,app.json,run.json}`.
7. Batch-write to the dashboard:
   - each app.json record goes to `candidates/<id>`;
   - run.json goes to `runs/run-NNN`.
8. Commit `campaigns/ott-qa` and push to `claude/inspiring-brown-3lh8cn`.
9. Report to the user: the new profiles table (immediate/open first) and the dashboard link.
