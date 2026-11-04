"""The collaboration workflow: MARK sources, JOE evaluates, the recruiter decides.

Gates enforced here (not just in the UI):
  * a campaign cannot hunt before the recruiter approves the search plan;
  * only the recruiter can move a candidate to 'submitted' or later stages;
  * a channel is 'connected' only with recorded evidence;
  * immediate-joiner status needs evidence, otherwise it is stored as unverified.
"""
from . import evaluate as joe
from . import hunt as mark
from . import intake
from . import skills as sk
from .db import new_id, norm_email, norm_url, now

STAGES = ["identified", "screened", "shortlisted", "submitted", "l1", "l2", "offered", "joined"]
EXITS = ["rejected", "on_hold", "withdrawn", "not_interested"]
RECRUITER_ONLY = {"submitted", "l1", "l2", "offered", "joined"}


def add_candidate(db, requirement_id, profile, actor="MARK", claims=None):
    """Store a sourced profile (no fabrication: name and a source are required), then JOE evaluates it."""
    req = intake.get(db, requirement_id)
    if req["status"] in ("intake", "plan_pending"):
        raise PermissionError("The search plan is not approved yet. Approve the plan before adding sourced profiles.")
    if not (profile.get("full_name") or "").strip():
        raise ValueError("A candidate needs a name taken from the source.")
    if not (profile.get("source_url") or profile.get("linkedin_url") or profile.get("resume_link") or profile.get("resume_text")):
        raise ValueError("A candidate needs a source: profile URL, resume link or resume text.")
    claims = dict(claims or {})
    exact, possible = joe.find_duplicates(db, profile)
    if exact:
        cid = exact[0]["id"]
        db.log("JOE", "duplicate_detected", {"existing": exact, "incoming": profile.get("full_name")}, requirement_id)
        existing = db.one("SELECT * FROM pipeline WHERE requirement_id=? AND candidate_id=?", (requirement_id, cid))
        if existing:
            return {"candidate_id": cid, "duplicate": True, "matched_on": exact[0]["on"], "evaluation": None}
        if profile.get("resume_text"):
            db.update_record("candidates", {"id": cid}, {"resume_text": profile["resume_text"]}, actor=actor)
    else:
        cid = new_id("CAN")
        verified = bool(profile.get("availability_evidence"))
        notice_status = profile.get("notice_status") or "unknown"
        if notice_status == "immediate" and not verified:
            claims["immediate_joiner"] = True
        otw = profile.get("open_to_work") or "unknown"
        if otw == "yes" and not profile.get("open_to_work_evidence"):
            claims["open_to_work"] = True
            otw = "claimed"
        db.insert("candidates", {
            "id": cid, "full_name": profile["full_name"].strip(), "current_company": profile.get("current_company"),
            "current_designation": profile.get("current_designation"), "total_exp_years": profile.get("total_exp_years"),
            "location": profile.get("location"), "notice_period_days": profile.get("notice_period_days"),
            "notice_status": notice_status, "availability_verified": int(verified),
            "availability_evidence": profile.get("availability_evidence"), "open_to_work": otw,
            "open_to_work_evidence": profile.get("open_to_work_evidence"),
            "linkedin_url": profile.get("linkedin_url"), "linkedin_norm": norm_url(profile.get("linkedin_url")),
            "github_url": profile.get("github_url"), "github_norm": norm_url(profile.get("github_url")),
            "email": profile.get("email"), "email_norm": norm_email(profile.get("email")),
            "resume_link": profile.get("resume_link"), "resume_text": profile.get("resume_text"),
            "source_channel": profile.get("source_channel"), "source_url": profile.get("source_url") or profile.get("linkedin_url"),
            "sourced_by": actor, "duplicate_of": possible[0]["id"] if possible else None,
            "created_at": now(), "updated_at": now()}, actor=actor)
        if possible:
            db.log("JOE", "possible_duplicate", {"candidate": cid, "matches": possible}, requirement_id)
    db.conn.execute("INSERT OR IGNORE INTO pipeline (requirement_id, candidate_id, status, source_channel, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (requirement_id, cid, "identified", profile.get("source_channel"), now(), now()))
    db.insert("candidate_status_history", {"requirement_id": requirement_id, "candidate_id": cid, "from_status": None,
                                           "to_status": "identified", "changed_by": actor, "note": "sourced", "at": now()}, audit=False)
    db.log("MARK", "profile_submitted_to_joe", {"candidate": cid, "name": profile["full_name"], "channel": profile.get("source_channel")}, requirement_id)
    result = run_evaluation(db, requirement_id, cid, claims)
    return {"candidate_id": cid, "duplicate": False, "possible_duplicates": possible, "evaluation": result}


def run_evaluation(db, requirement_id, candidate_id, claims=None):
    lib = sk.library(db)
    req = intake.get(db, requirement_id)
    cand = db.one("SELECT * FROM candidates WHERE id=?", (candidate_id,))
    if not cand.get("resume_text"):
        db.log("JOE", "evaluation_deferred", {"candidate": candidate_id, "reason": "no resume text"}, requirement_id)
        return None
    res = joe.evaluate(req, cand, lib)
    res["challenges"] = joe.cross_check(req, cand, res, claims)
    db.insert("resume_evaluations", {
        "requirement_id": requirement_id, "candidate_id": candidate_id, "total": res["total"], "classification": res["classification"],
        "recommendation": res["recommendation"], "breakdown": res["breakdown"], "skill_evidence": res["skill_evidence"],
        "missing_skills": res["missing_skills"], "critical_gaps": res["critical_gaps"], "flags": res["flags"],
        "screening_questions": res["screening_questions"], "relevant_exp_years": res["relevant_exp_years"],
        "total_exp_years": res["total_exp_years"], "challenges": res["challenges"], "weights": res["weights"], "created_at": now()}, actor="JOE", audit=False)
    db.conn.execute("DELETE FROM candidate_skills WHERE candidate_id=?", (candidate_id,))
    for s, e in res["skill_evidence"].items():
        if e["level"]:
            db.conn.execute("INSERT INTO candidate_skills (candidate_id, skill, level, levels, evidence, confidence, created_at) VALUES (?,?,?,?,?,?,?)",
                            (candidate_id, s, e["level"], db._enc("levels", e["levels"]), e["evidence"][0]["text"] if e["evidence"] else None, e["confidence"], now()))
    db.conn.execute("DELETE FROM candidate_projects WHERE candidate_id=?", (candidate_id,))
    for r in joe.experience(cand["resume_text"])["roles"]:
        tech = sk.find_skills(r["block"], lib)
        db.conn.execute("INSERT INTO candidate_projects (candidate_id, title, start, end, months, technologies, description, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (candidate_id, r["header"][:200], f"{r['start'] // 12}-{r['start'] % 12 + 1:02d}", f"{r['end'] // 12}-{r['end'] % 12 + 1:02d}",
                         r["months"], db._enc("technologies", tech), r["block"][:1500], now()))
    if res["total_exp_years"] is not None and cand.get("total_exp_years") is None:
        db.conn.execute("UPDATE candidates SET total_exp_years=? WHERE id=?", (res["total_exp_years"], candidate_id))
    p = db.one("SELECT * FROM pipeline WHERE requirement_id=? AND candidate_id=?", (requirement_id, candidate_id))
    summary = {"recommendation": res["recommendation"], "missing": res["missing_skills"], "critical_gaps": res["critical_gaps"],
               "keyword_only": res["keyword_only"], "flags": [f["text"] for f in res["flags"]]}
    db.conn.execute("UPDATE pipeline SET match_score=?, classification=?, joe_assessment=?, updated_at=? WHERE requirement_id=? AND candidate_id=?",
                    (res["total"], res["classification"], db._enc("joe_assessment", summary), now(), requirement_id, candidate_id))
    db.conn.commit()
    if p and p["status"] == "identified":
        set_status(db, requirement_id, candidate_id, "screened", actor="JOE", note="JOE evaluated the resume")
        if res["total"] >= 70 and not res["critical_gaps"]:
            set_status(db, requirement_id, candidate_id, "shortlisted", actor="JOE", note=res["recommendation"])
        elif res["total"] < 55:
            set_status(db, requirement_id, candidate_id, "rejected", actor="JOE", note="Below 55: not recommended")
    db.log("JOE", "profile_evaluated", {"candidate": candidate_id, "score": res["total"], "classification": res["classification"],
                                        "recommendation": res["recommendation"], "challenges": len(res["challenges"])}, requirement_id)
    for c in res["challenges"]:
        db.log(c["by"], "challenge", {"candidate": candidate_id, "to": c["to"], "text": c["text"]}, requirement_id)
    if req["status"] == "hunting":
        db.update_record("requirements", {"id": requirement_id}, {"status": "evaluating"}, actor="JOE")
    return res


def set_status(db, requirement_id, candidate_id, status, actor="recruiter", note=None):
    if status not in STAGES + EXITS:
        raise ValueError(f"Unknown status {status}")
    if status in RECRUITER_ONLY and not actor.startswith("recruiter"):
        raise PermissionError(f"Only the recruiter can move a candidate to '{status}'. Agents never submit profiles.")
    p = db.one("SELECT * FROM pipeline WHERE requirement_id=? AND candidate_id=?", (requirement_id, candidate_id))
    if not p:
        raise KeyError("Candidate is not in this requirement's pipeline.")
    changes = {"status": status}
    if status == "submitted":
        changes["recruiter_approved_submit"] = 1
    db.update_record("pipeline", {"requirement_id": requirement_id, "candidate_id": candidate_id}, changes, actor=actor)
    db.insert("candidate_status_history", {"requirement_id": requirement_id, "candidate_id": candidate_id, "from_status": p["status"],
                                           "to_status": status, "changed_by": actor, "note": note, "at": now()}, audit=False)
    return status


def update_candidate(db, candidate_id, changes, actor="recruiter"):
    allowed = {"full_name", "current_company", "current_designation", "total_exp_years", "location", "notice_period_days",
               "notice_status", "availability_evidence", "open_to_work", "open_to_work_evidence", "linkedin_url", "github_url",
               "email", "resume_link", "resume_text", "source_channel"}
    ch = {k: v for k, v in changes.items() if k in allowed}
    if "linkedin_url" in ch:
        ch["linkedin_norm"] = norm_url(ch["linkedin_url"])
    if "github_url" in ch:
        ch["github_norm"] = norm_url(ch["github_url"])
    if "email" in ch:
        ch["email_norm"] = norm_email(ch["email"])
    if "availability_evidence" in ch:
        ch["availability_verified"] = int(bool(ch["availability_evidence"]))
    return db.update_record("candidates", {"id": candidate_id}, ch, actor=actor)


def add_remark(db, requirement_id, candidate_id, remark, rating=None, actor="recruiter"):
    db.update_record("pipeline", {"requirement_id": requirement_id, "candidate_id": candidate_id}, {"recruiter_remarks": remark}, actor=actor)
    p = db.one("SELECT source_channel FROM pipeline WHERE requirement_id=? AND candidate_id=?", (requirement_id, candidate_id))
    ch = db.one("SELECT id FROM sourcing_channels WHERE name=?", (p["source_channel"],)) if p and p["source_channel"] else None
    db.insert("recruiter_feedback", {"requirement_id": requirement_id, "candidate_id": candidate_id, "channel_id": ch["id"] if ch else None,
                                     "rating": rating, "feedback": remark, "at": now()}, actor=actor, audit=False)


def upsert_channel(db, name, category="Custom", methodology=None, filters=None, actor="recruiter"):
    c = db.one("SELECT * FROM sourcing_channels WHERE name=?", (name,))
    if c:
        ch = {k: v for k, v in {"category": category, "methodology": methodology, "filters": filters}.items() if v}
        return db.update_record("sourcing_channels", {"id": c["id"]}, ch, actor=actor) if ch else c
    cid = new_id("CH")
    db.insert("sourcing_channels", {"id": cid, "name": name, "category": category, "connected": 0, "access_permission": "not confirmed",
                                    "methodology": methodology, "filters": filters or [], "manual_only": 1, "active": 1, "approved": 0,
                                    "date_added": now()}, actor=actor)
    return db.one("SELECT * FROM sourcing_channels WHERE id=?", (cid,))


def set_channel_active(db, channel_id, active, actor="recruiter"):
    """Deactivate, never delete: history stays."""
    return db.update_record("sourcing_channels", {"id": channel_id}, {"active": int(bool(active))}, actor=actor)


def set_channel_connection(db, channel_id, connected, evidence, access=None, actor="recruiter"):
    if connected and not evidence:
        raise ValueError("Say how the connection was confirmed (e.g. 'test search returned results in session 2026-11-04').")
    return db.update_record("sourcing_channels", {"id": channel_id}, {"connected": int(bool(connected)), "connection_evidence": evidence,
                                                                      "connection_verified_at": now() if connected else None,
                                                                      "access_permission": access or ("confirmed" if connected else "not confirmed")}, actor=actor)


def verify_connector(db, name, status, actions=None, bulk=False, evidence=None, permissions=None, actor="recruiter"):
    if status == "connected" and not evidence:
        raise ValueError("A connector is marked connected only with evidence of a successful call.")
    c = db.one("SELECT * FROM connector_registry WHERE name=?", (name,))
    ch = {"status": status, "evidence": evidence, "verified_at": now(), "verified_by": actor}
    if actions is not None:
        ch["supported_actions"] = actions
    if permissions:
        ch["permissions"] = permissions
    ch["bulk_sourcing"] = int(bool(bulk))
    if not c:
        db.insert("connector_registry", {"id": new_id("CN"), "name": name, "category": "Custom", **ch}, actor=actor)
        return db.one("SELECT * FROM connector_registry WHERE name=?", (name,))
    return db.update_record("connector_registry", {"id": c["id"]}, ch, actor=actor)


def final_shortlist(db, requirement_id):
    """Both agents' view: shortlisted, no critical gaps, sorted by score, capped at the requested number."""
    req = intake.get(db, requirement_id)
    rows = db.q("""SELECT c.*, p.status, p.match_score, p.classification, p.joe_assessment, p.source_channel AS pipeline_channel
                   FROM pipeline p JOIN candidates c ON c.id=p.candidate_id
                   WHERE p.requirement_id=? AND p.status IN ('shortlisted','submitted','l1','l2','offered','joined')
                   ORDER BY p.match_score DESC""", (requirement_id,))
    clean = [r for r in rows if not (r["joe_assessment"] or {}).get("critical_gaps")]
    n = req.get("profiles_required") or len(clean)
    db.log("MARK", "final_shortlist", {"count": min(n, len(clean))}, requirement_id)
    return clean[:n]


def plan(db, requirement_id):
    return mark.build_plan(db, intake.get(db, requirement_id))
