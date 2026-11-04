"""Command line for the MARK & JOE command centre (used by recruiters and by Claude sessions acting as MARK/JOE).

  python3 -m markjoe.cli jd new jd.txt                 # MARK reads the JD, prints the first question
  python3 -m markjoe.cli ask REQ-1234                  # next question (one at a time)
  python3 -m markjoe.cli answer REQ-1234 "5-8 years"
  python3 -m markjoe.cli channels list [--family data_engineering]
  python3 -m markjoe.cli channels confirm REQ-1234 "LinkedIn Recruiter" "Google X-Ray"
  python3 -m markjoe.cli channels add "Hasgeek community" --category Community
  python3 -m markjoe.cli plan REQ-1234                 # proposed plan (JSON)
  python3 -m markjoe.cli approve REQ-1234 --by "Pravin"  # recruiter approval only
  python3 -m markjoe.cli search log REQ-1234 "Google X-Ray" --query "..." --results 12 --evidence "..."
  python3 -m markjoe.cli candidate add REQ-1234 profiles.json   # one profile or a list
  python3 -m markjoe.cli status REQ-1234 CAN-ABCD submitted --recruiter "Pravin"
  python3 -m markjoe.cli refine REQ-1234 | shortlist REQ-1234
  python3 -m markjoe.cli connector set "The Org" connected --evidence "find_positions returned 25 rows 2026-11-04" --actions "people search,org chart"
  python3 -m markjoe.cli export xlsx out.xlsx [--req REQ-1234]
  python3 -m markjoe.cli state [--req REQ-1234]
  python3 -m markjoe.cli serve [--port 8765]
"""
import argparse
import json
import sys

from . import analytics, export, hunt, intake, server, service
from . import skills as sk
from .db import DB


def out(x):
    print(json.dumps(x, indent=1, default=str, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="markjoe", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init")
    j = sp.add_parser("jd"); j.add_argument("action", choices=["new"]); j.add_argument("file")
    a = sp.add_parser("ask"); a.add_argument("req")
    a = sp.add_parser("answer"); a.add_argument("req"); a.add_argument("text"); a.add_argument("--key")
    c = sp.add_parser("channels"); c.add_argument("action", choices=["list", "confirm", "add", "deactivate", "connect"]); c.add_argument("args", nargs="*")
    c.add_argument("--family"); c.add_argument("--category", default="Custom"); c.add_argument("--methodology"); c.add_argument("--evidence"); c.add_argument("--url")
    c.add_argument("--string-type", choices=["boolean", "xray", "github"])
    for n in ("plan", "refine", "shortlist", "show"):
        x = sp.add_parser(n); x.add_argument("req")
    x = sp.add_parser("approve"); x.add_argument("req"); x.add_argument("--by", required=True, help="recruiter name (approval is never given by an agent)")
    s = sp.add_parser("search"); s.add_argument("action", choices=["log"]); s.add_argument("req"); s.add_argument("channel")
    s.add_argument("--query", default=""); s.add_argument("--results", type=int, default=0); s.add_argument("--evidence", required=True); s.add_argument("--by", default="MARK")
    k = sp.add_parser("candidate"); k.add_argument("action", choices=["add", "show", "evaluate"]); k.add_argument("a"); k.add_argument("b", nargs="?")
    st = sp.add_parser("status"); st.add_argument("req"); st.add_argument("cand"); st.add_argument("status"); st.add_argument("--recruiter"); st.add_argument("--note")
    co = sp.add_parser("connector"); co.add_argument("action", choices=["set", "list"]); co.add_argument("name", nargs="?"); co.add_argument("status", nargs="?")
    co.add_argument("--evidence"); co.add_argument("--actions"); co.add_argument("--bulk", action="store_true")
    e = sp.add_parser("export"); e.add_argument("fmt", choices=["csv", "xlsx"]); e.add_argument("path"); e.add_argument("--req")
    x = sp.add_parser("state"); x.add_argument("--req")
    x = sp.add_parser("serve"); x.add_argument("--port", type=int, default=8765); x.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        return server.main(["--port", str(a.port), "--host", a.host] + (["--db", a.db] if a.db else []))
    db = DB(a.db)
    db.seed()
    if a.cmd == "init":
        return print(f"Database ready at {db.path}")
    if a.cmd == "jd":
        r = intake.create_requirement(db, open(a.file).read())
        return out({"requirement": r["id"], "understood": r["intake"]["from_jd"], "family": r["job_family"],
                    "warnings": intake.market_warnings(r, sk.library(db)),
                    "next_question": intake.next_question(db, r)})
    if a.cmd == "ask":
        r = intake.get(db, a.req)
        return out({"next_question": intake.next_question(db, r), "ready_for_plan": intake.ready_for_plan(db, r)})
    if a.cmd == "answer":
        r, q, info = intake.answer(db, a.req, a.text, a.key)
        return out({"info": info, "next_question": q, "ready_for_plan": intake.ready_for_plan(db, r)})
    if a.cmd == "show":
        return out(server.requirement_view(db, a.req))
    if a.cmd == "channels":
        if a.action == "list":
            return out([{k: c[k] for k in ("id", "name", "url", "category", "connected", "approved", "active", "memory_entries", "date_last_used")} for c in hunt.channel_memory(db, a.family)])
        if a.action == "confirm":
            req = intake.get(db, a.args[0])
            ids = []
            for n in a.args[1:]:
                ch = db.one("SELECT id FROM sourcing_channels WHERE lower(name)=lower(?)", (n,))
                if not ch:
                    sys.exit(f"Unknown channel: {n}. Add it with 'channels add'.")
                ids.append(ch["id"])
            hunt.confirm_channels(db, req, ids)
            return out({"confirmed": a.args[1:]})
        if a.action == "add":
            return out(service.upsert_channel(db, a.args[0], a.category, a.methodology, url=a.url, string_type=a.string_type))
        ch = db.one("SELECT id FROM sourcing_channels WHERE lower(name)=lower(?)", (a.args[0],))
        if a.action == "deactivate":
            return out(service.set_channel_active(db, ch["id"], False))
        return out(service.set_channel_connection(db, ch["id"], True, a.evidence))
    if a.cmd == "plan":
        req = intake.get(db, a.req)
        if not intake.ready_for_plan(db, req):
            sys.exit("MARK still needs essential answers: run 'ask'.")
        if not req["intake"].get("channels"):
            sys.exit("Confirm channels first: 'channels confirm'.")
        return out(service.plan(db, a.req))
    if a.cmd == "approve":
        return out(hunt.approve_plan(db, intake.get(db, a.req), actor=f"recruiter:{a.by}")["version"])
    if a.cmd == "search":
        ch = db.one("SELECT id FROM sourcing_channels WHERE lower(name)=lower(?)", (a.channel,))
        hunt.log_search(db, a.req, ch["id"], a.query, a.results, a.evidence, a.by)
        return out({"logged": True})
    if a.cmd == "candidate":
        if a.action == "add":
            data = json.load(open(a.b))
            res = [service.add_candidate(db, a.a, p) for p in (data if isinstance(data, list) else [data])]
            return out([{"candidate_id": r["candidate_id"], "duplicate": r["duplicate"],
                         "score": (r.get("evaluation") or {}).get("total"), "recommendation": (r.get("evaluation") or {}).get("recommendation"),
                         "critical_gaps": (r.get("evaluation") or {}).get("critical_gaps")} for r in res])
        if a.action == "evaluate":
            return out(service.run_evaluation(db, a.a, a.b))
        return out(server.candidate_view(db, a.a))
    if a.cmd == "status":
        actor = f"recruiter:{a.recruiter}" if a.recruiter else "MARK"
        return out(service.set_status(db, a.req, a.cand, a.status, actor=actor, note=a.note))
    if a.cmd == "refine":
        return out(hunt.refine(db, intake.get(db, a.req)))
    if a.cmd == "shortlist":
        return out([{k: c[k] for k in ("id", "full_name", "current_company", "match_score", "status", "linkedin_url")} for c in service.final_shortlist(db, a.req)])
    if a.cmd == "connector":
        if a.action == "list":
            return out(db.q("SELECT name, category, status, supported_actions, bulk_sourcing, evidence, verified_at FROM connector_registry"))
        acts = [x.strip() for x in a.actions.split(",")] if a.actions else None
        return out(service.verify_connector(db, a.name, a.status, acts, a.bulk, a.evidence, actor="recruiter"))
    if a.cmd == "export":
        rows = analytics.candidate_rows(db, {"requirement": a.req} if a.req else {})
        open(a.path, "wb").write(export.to_csv(rows) if a.fmt == "csv" else export.to_xlsx(rows))
        return print(f"Wrote {len(rows)} rows to {a.path}")
    if a.cmd == "state":
        s = analytics.state(db, {"requirement": a.req} if a.req else {})
        return out({k: s[k] for k in ("overview", "funnel", "channel_performance", "best_channel")})


if __name__ == "__main__":
    main()
