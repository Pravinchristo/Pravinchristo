# Automated Recruitment Tracker (Excel)

| File | What it is |
|---|---|
| `Recruitment_Tracker.xlsx` | Tracker with demo data: 6 requisitions and 40 candidates, so you can see every automation working |
| `Recruitment_Tracker_Template.xlsx` | Clean copy with one example row, ready for real use |
| `build_tracker.py` | Rebuilds both files (`python build_tracker.py` / `python build_tracker.py --blank`) |

## Sheets
- **How To Use**: a short guide.
- **Dashboard**: 12 KPI tiles, hiring funnel with stage-to-stage conversion, current stage snapshot with SLA breaches, source effectiveness, recruiter performance, monthly trend, requisition health and 3 charts. All of it is formulas, so there is nothing to edit.
- **Requisitions**: you enter the role details. The sheet calculates candidates, active pipeline, offers, joined, openings left, fill %, days open, days to target and status (Open / Overdue / No Pipeline / Filled).
- **Candidates**: you enter candidate details and the current stage. The sheet calculates the candidate ID, role and hiring manager lookup, pipeline status, hike %, days in pipeline and in stage, SLA status, next action, expected joining date, time to offer and time to hire.
- **Lists**: stages, SLA days, next-action text, sources, recruiters, departments and locations. Every dropdown and rule reads from here.

Cream cells / navy headers = you type. Light-blue cells / teal headers = automatic.
The rows are set up for 500 candidates and 100 requisitions. Day counts use `TODAY()`, so they update every time the file is opened.
