"""Local HTTP API + dashboard. Standard library only.

    python3 -m markjoe.server [--port 8765] [--db path]

Binds to 127.0.0.1 by default so candidate data stays on this machine. Set
MARKJOE_TOKEN to require an `X-MarkJoe-Token` header on every API call.
"""
import argparse
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import analytics, export, hunt, intake, service
from . import skills as sk
from .db import DB

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
LOCK = threading.RLock()


def requirement_view(db, rid):
    lib = sk.library(db)
    req = intake.get(db, rid)
    plan = db.one("SELECT * FROM search_strategies WHERE requirement_id=? ORDER BY version DESC", (rid,))
    return {"requirement": req, "next_question": intake.next_question(db, req), "ready_for_plan": intake.ready_for_plan(db, req),
            "pending": intake.pending_questions(req, lib), "warnings": intake.market_warnings(req, lib),
            "skill_intelligence": sk.intelligence(req["mandatory_skills"], req["preferred_skills"], req["job_family"], lib),
            "plan": plan, "channel_memory": hunt.channel_memory(db, req["job_family"]),
            "connectors": db.q("SELECT * FROM connector_registry ORDER BY category, name")}


def candidate_view(db, cid):
    c = db.one("SELECT * FROM candidates WHERE id=?", (cid,))
    if not c:
        raise KeyError(cid)
    return {"candidate": c,
            "pipelines": db.q("SELECT p.*, r.title FROM pipeline p JOIN requirements r ON r.id=p.requirement_id WHERE candidate_id=?", (cid,)),
            "evaluations": db.q("SELECT * FROM resume_evaluations WHERE candidate_id=? ORDER BY id DESC", (cid,)),
            "skills": db.q("SELECT * FROM candidate_skills WHERE candidate_id=?", (cid,)),
            "projects": db.q("SELECT * FROM candidate_projects WHERE candidate_id=? ORDER BY start DESC", (cid,)),
            "history": db.q("SELECT * FROM candidate_status_history WHERE candidate_id=? ORDER BY id", (cid,)),
            "audit": db.q("SELECT * FROM audit_log WHERE entity='candidates' AND entity_id LIKE ? ORDER BY id DESC LIMIT 50", (f"%{cid}%",))}


class Handler(BaseHTTPRequestHandler):
    db = None
    token = None

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        return not self.token or self.headers.get("X-MarkJoe-Token") == self.token or parse_qs(urlparse(self.path).query).get("token", [None])[0] == self.token

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, open(os.path.join(WEB, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if u.path in ("/mark.svg", "/joe.svg"):
            return self._send(200, open(os.path.join(WEB, u.path[1:]), "rb").read(), "image/svg+xml")
        self._api("GET", u)

    def do_POST(self):
        self._api("POST", urlparse(self.path))

    def _api(self, method, u):
        if not u.path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        if not self._auth():
            return self._send(401, {"error": "token required"})
        qs = {k: v[0] for k, v in parse_qs(u.query).items() if k != "token"}
        try:
            with LOCK:
                body = self._body() if method == "POST" else {}
                out = route(self.db, method, u.path[5:].strip("/").split("/"), qs, body)
            if isinstance(out, tuple):
                return self._send(200, out[0], out[1], out[2])
            return self._send(200, out)
        except PermissionError as e:
            return self._send(403, {"error": str(e)})
        except (KeyError, LookupError) as e:
            return self._send(404, {"error": f"not found: {e}"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # noqa
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})


def route(db, m, p, qs, b):
    r = lambda: intake.get(db, p[1])  # noqa
    if m == "GET" and p == ["state"]:
        return analytics.state(db, qs)
    if m == "GET" and p[0] in ("export.csv", "export.xlsx"):
        rows = analytics.candidate_rows(db, qs)
        if p[0] == "export.csv":
            return export.to_csv(rows), "text/csv; charset=utf-8", {"Content-Disposition": "attachment; filename=markjoe-candidates.csv"}
        return export.to_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", {"Content-Disposition": "attachment; filename=markjoe-candidates.xlsx"}
    if p[0] == "requirements":
        if m == "POST" and len(p) == 1:
            if not (b.get("jd_text") or "").strip():
                raise ValueError("Paste a job description first.")
            req = intake.create_requirement(db, b["jd_text"])
            return requirement_view(db, req["id"])
        if m == "GET" and len(p) == 2:
            return requirement_view(db, p[1])
        if m == "POST" and len(p) == 3:
            act = p[2]
            if act == "answer":
                _, _, info = intake.answer(db, p[1], b.get("answer", ""), b.get("key"))
                v = requirement_view(db, p[1])
                v["info"] = info
                return v
            if act == "channels":
                hunt.confirm_channels(db, r(), b.get("channel_ids") or [])
                return requirement_view(db, p[1])
            if act == "plan":
                if not intake.ready_for_plan(db, r()):
                    raise ValueError("MARK still needs the essential answers before proposing a plan.")
                if not (r()["intake"].get("channels")):
                    raise ValueError("Confirm sourcing channels first.")
                service.plan(db, p[1])
                return requirement_view(db, p[1])
            if act == "approve":
                hunt.approve_plan(db, r())
                return requirement_view(db, p[1])
            if act == "refine":
                return hunt.refine(db, r())
            if act == "shortlist":
                return {"shortlist": service.final_shortlist(db, p[1])}
            if act == "status":
                if b.get("status") not in ("intake", "plan_pending", "hunting", "evaluating", "shortlisted", "on_hold", "closed"):
                    raise ValueError("Unknown requirement status.")
                db.update_record("requirements", {"id": p[1]}, {"status": b["status"]})
                return requirement_view(db, p[1])
            if act == "update":
                allowed = {"title", "exp_min", "exp_max", "location", "work_mode", "salary_budget", "notice_max_days", "domain",
                           "education", "profiles_required", "mandatory_skills", "preferred_skills", "critical_skills", "weights"}
                db.update_record("requirements", {"id": p[1]}, {k: v for k, v in b.items() if k in allowed})
                return requirement_view(db, p[1])
    if p[0] == "candidates":
        if m == "POST" and len(p) == 1:
            return service.add_candidate(db, b["requirement_id"], b.get("profile") or {}, actor=b.get("actor", "MARK") if b.get("actor") in ("MARK", "recruiter") else "MARK", claims=b.get("claims"))
        if m == "GET" and len(p) == 2:
            return candidate_view(db, p[1])
        if m == "POST" and len(p) == 2:
            service.update_candidate(db, p[1], b)
            return candidate_view(db, p[1])
        if m == "POST" and len(p) == 3 and p[2] == "evaluate":
            return service.run_evaluation(db, b["requirement_id"], p[1])
    if m == "POST" and p == ["pipeline"]:
        service.set_status(db, b["requirement_id"], b["candidate_id"], b["status"], actor="recruiter", note=b.get("note"))
        return {"ok": True}
    if m == "POST" and p == ["remarks"]:
        service.add_remark(db, b["requirement_id"], b["candidate_id"], b.get("remark", ""), b.get("rating"))
        return {"ok": True}
    if p[0] == "channels":
        if m == "GET":
            return hunt.channel_memory(db, qs.get("family"))
        if m == "POST" and len(p) == 1:
            return service.upsert_channel(db, b["name"].strip(), b.get("category") or "Custom", b.get("methodology"), b.get("filters"),
                                         url=b.get("url") or None, string_type=b.get("string_type") or None)
        if m == "POST" and len(p) == 2:
            if "active" in b:
                service.set_channel_active(db, p[1], b["active"])
            if "connected" in b:
                service.set_channel_connection(db, p[1], b["connected"], b.get("evidence"), b.get("access"))
            if b.get("feedback"):
                db.update_record("sourcing_channels", {"id": p[1]}, {"recruiter_feedback": b["feedback"]})
            return db.one("SELECT * FROM sourcing_channels WHERE id=?", (p[1],))
    if m == "POST" and p == ["connectors"]:
        return service.verify_connector(db, b["name"], b["status"], b.get("actions"), b.get("bulk", False), b.get("evidence"), b.get("permissions"))
    if m == "POST" and p == ["searches"]:
        hunt.log_search(db, b["requirement_id"], b["channel_id"], b.get("query", ""), int(b.get("results_count") or 0), b.get("evidence"), "recruiter")
        return {"ok": True}
    if m == "GET" and p == ["audit"]:
        return db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(qs.get("limit", 200)),))
    if m == "POST" and p == ["skills"]:
        return sk.add_skill(db, b["name"], b.get("aliases"), b.get("equivalents"), b.get("related"), b.get("family", "general"))
    raise LookupError("/".join(p))


def main(argv=None):
    ap = argparse.ArgumentParser(description="MARK & JOE command centre")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = DB(a.db)
    db.seed()
    Handler.db = db
    Handler.token = os.environ.get("MARKJOE_TOKEN")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"MARK & JOE command centre on http://{a.host}:{a.port}  (db: {db.path})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
