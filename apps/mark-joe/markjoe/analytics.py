"""Dashboard metrics, computed only from stored records. No sample data."""
from collections import Counter, defaultdict

from . import skills as sk
from .db import now
from .service import STAGES

REACHED = {s: i for i, s in enumerate(STAGES)}


def _reached(db, req_id=None):
    """Furthest funnel stage each (requirement, candidate) reached, from status history."""
    sql = "SELECT requirement_id, candidate_id, to_status FROM candidate_status_history"
    rows = db.q(sql + (" WHERE requirement_id=?" if req_id else ""), (req_id,) if req_id else ())
    best = {}
    for r in rows:
        k = (r["requirement_id"], r["candidate_id"])
        i = REACHED.get(r["to_status"], -1)
        best[k] = max(best.get(k, -1), i)
    return best


def candidate_rows(db, f=None):
    f = f or {}
    rows = db.q("""SELECT p.requirement_id, r.title AS requirement_title, p.status, p.match_score, p.classification, p.joe_assessment,
                          p.recruiter_remarks, p.source_channel, c.*,
                          (SELECT relevant_exp_years FROM resume_evaluations e WHERE e.candidate_id=c.id AND e.requirement_id=p.requirement_id ORDER BY e.id DESC LIMIT 1) AS relevant_exp_years
                   FROM pipeline p JOIN candidates c ON c.id=p.candidate_id JOIN requirements r ON r.id=p.requirement_id
                   ORDER BY p.match_score DESC""")
    skills = defaultdict(list)
    for s in db.q("SELECT candidate_id, skill, level FROM candidate_skills"):
        skills[s["candidate_id"]].append({"skill": s["skill"], "level": s["level"]})
    out = []
    for r in rows:
        r.pop("resume_text", None)
        r.pop("email", None)  # contact details stay out of the dashboard payload
        r.pop("email_norm", None)
        r["skills"] = skills.get(r["id"], [])
        r["availability"] = availability_label(r)
        if not _match(r, f):
            continue
        out.append(r)
    return out


def availability_label(c):
    if c.get("availability_verified") and (c.get("notice_status") == "immediate" or c.get("notice_period_days") == 0):
        return "Immediate (verified)"
    if c.get("notice_status") == "serving":
        return "Serving notice" + (" (verified)" if c.get("availability_verified") else " (unverified)")
    if c.get("notice_period_days") is not None:
        return f"{c['notice_period_days']} days" + (" (verified)" if c.get("availability_verified") else " (claimed)")
    return "Unknown"


def _match(r, f):
    def has(k):
        return f.get(k) not in (None, "", [])
    if has("requirement") and r["requirement_id"] != f["requirement"]:
        return False
    if has("title") and f["title"].lower() not in (r["requirement_title"] or "").lower() and f["title"].lower() not in (r["current_designation"] or "").lower():
        return False
    if has("skill") and not any(f["skill"].lower() == s["skill"].lower() for s in r["skills"]):
        return False
    if has("location") and f["location"].lower() not in (r["location"] or "").lower():
        return False
    if has("company") and f["company"].lower() not in (r["current_company"] or "").lower():
        return False
    if has("channel") and (r["source_channel"] or "") != f["channel"]:
        return False
    if has("status") and r["status"] != f["status"]:
        return False
    if has("availability") and not (r["availability"] or "").lower().startswith(f["availability"].lower()):
        return False
    if has("min_score") and (r["match_score"] or 0) < float(f["min_score"]):
        return False
    if has("min_exp") and (r["total_exp_years"] or 0) < float(f["min_exp"]):
        return False
    if has("max_exp") and (r["total_exp_years"] or 0) > float(f["max_exp"]):
        return False
    if has("max_notice") and (r["notice_period_days"] is None or r["notice_period_days"] > int(f["max_notice"])):
        return False
    return True


def state(db, f=None):
    f = f or {}
    req_id = f.get("requirement") or None
    lib = sk.library(db)
    reqs = db.q("SELECT * FROM requirements ORDER BY created_at DESC")
    for r in reqs:
        r.pop("jd_text", None)
    cands = candidate_rows(db, f)
    keys = {(c["requirement_id"], c["id"]) for c in cands}
    reached = {k: v for k, v in _reached(db, req_id).items() if k in keys}
    stage_counts = [sum(1 for v in reached.values() if v >= i) for i in range(len(STAGES))]
    uniq = {c["id"]: c for c in cands}

    overview = {
        "active_requirements": sum(1 for r in reqs if r["status"] not in ("closed", "on_hold")),
        "profiles_sourced": len(uniq),
        "profiles_screened": sum(1 for c in cands if c["match_score"] is not None),
        "relevant": sum(1 for c in cands if (c["match_score"] or 0) >= 55),
        "high_potential": sum(1 for c in cands if (c["match_score"] or 0) >= 85),
        "open_to_work": sum(1 for c in uniq.values() if c["open_to_work"] == "yes"),
        "immediate_joiners": sum(1 for c in uniq.values() if c["availability"] == "Immediate (verified)"),
        "submitted": stage_counts[3], "interviewed": stage_counts[4], "offers": stage_counts[6], "joined": stage_counts[7],
        "note": "Open to Work and immediate joiners count only candidates with recorded evidence.",
    }
    funnel = [{"stage": s, "count": stage_counts[i]} for i, s in enumerate(STAGES)]

    # channel performance
    perf = {}
    for c in cands:
        ch = c["source_channel"] or "Unknown"
        d = perf.setdefault(ch, {"channel": ch, "sourced": 0, "relevant": 0, "shortlisted": 0, "interviews": 0, "offers": 0, "joined": 0})
        d["sourced"] += 1
        d["relevant"] += (c["match_score"] or 0) >= 55
        st = reached.get((c["requirement_id"], c["id"]), -1)
        d["shortlisted"] += st >= 2
        d["interviews"] += st >= 4
        d["offers"] += st >= 6
        d["joined"] += st >= 7
    searches = Counter(r["channel_id"] for r in db.q("SELECT channel_id FROM search_runs" + (" WHERE requirement_id=?" if req_id else ""), (req_id,) if req_id else ()))
    channels = db.q("SELECT * FROM sourcing_channels ORDER BY name")
    for ch in channels:
        d = perf.get(ch["name"])
        ch["logged_searches"] = searches.get(ch["id"], 0)
        if d:
            d["logged_searches"] = searches.get(ch["id"], 0)
    for d in perf.values():
        s = d["sourced"] or 1
        d["relevance_rate"] = round(d["relevant"] / s * 100)
        d["interview_rate"] = round(d["interviews"] / s * 100)
        d["offer_rate"] = round(d["offers"] / s * 100)
        d["join_rate"] = round(d["joined"] / s * 100)
        # performance score: relevance 40%, shortlist 30%, interview 20%, join 10%, damped for tiny samples
        raw = 40 * d["relevant"] / s + 30 * d["shortlisted"] / s + 20 * d["interviews"] / s + 10 * d["joined"] / s
        d["score"] = round(raw * min(1, d["sourced"] / 5), 1)
    perf_list = sorted(perf.values(), key=lambda d: -d["score"])
    best = perf_list[0]["channel"] if perf_list and perf_list[0]["sourced"] >= 3 else None

    # company mapping
    maps = db.q("""SELECT m.*, t.name, t.category, t.verified, t.tech_ecosystem FROM company_talent_maps m JOIN target_companies t ON t.id=m.company_id
                   """ + ("WHERE m.requirement_id=? " if req_id else "") + "ORDER BY m.relevance DESC", (req_id,) if req_id else ())
    by_company = Counter((c["current_company"] or "Unknown") for c in uniq.values())
    seen = {}
    for m in maps:
        if m["name"] in seen:
            continue
        m["candidates"] = by_company.get(m["name"], 0)
        seen[m["name"]] = m
    companies = list(seen.values())[:40]
    distribution = [{"company": k, "count": v} for k, v in by_company.most_common(15)]

    # skill intelligence
    focus = [r for r in reqs if r["id"] == req_id] if req_id else reqs
    mand = list(dict.fromkeys(s for r in focus for s in (r["mandatory_skills"] or [])))
    pref = list(dict.fromkeys(s for r in focus for s in (r["preferred_skills"] or []) if s not in mand))
    n = len(uniq) or 1

    def coverage(sk_list):
        out = []
        for s in sk_list:
            lv = Counter(next((x["level"] for x in c["skills"] if x["skill"] == s), None) for c in uniq.values())
            proven = sum(v for k, v in lv.items() if k and k != "mentioned")
            out.append({"skill": s, "proven": proven, "keyword_only": lv.get("mentioned", 0), "missing": len(uniq) - proven - lv.get("mentioned", 0),
                        "proven_pct": round(proven / n * 100)})
        return out
    combos = Counter()
    for c in uniq.values():
        have = sorted(x["skill"] for x in c["skills"] if x["skill"] in mand and x["level"] != "mentioned")
        if len(have) >= 2:
            combos[" + ".join(have)] += 1
    dist = Counter(x["skill"] for c in uniq.values() for x in c["skills"] if x["level"] != "mentioned")
    gaps = Counter(g for c in cands for g in ((c["joe_assessment"] or {}).get("missing") or []))
    alt = []
    for r in focus:
        for t in sk.intelligence(r["mandatory_skills"] or [], [], r["job_family"], lib)["transferable"][:8]:
            alt.append({**t, "candidates_with_it": dist.get(t["skill"], 0)})
    skill_intel = {"mandatory": coverage(mand), "secondary": coverage(pref), "combinations": [{"combo": k, "count": v} for k, v in combos.most_common(8)],
                   "distribution": [{"skill": k, "count": v} for k, v in dist.most_common(15)],
                   "gaps": [{"skill": k, "count": v} for k, v in gaps.most_common(10)], "alternatives": alt[:12]}

    # agent activity
    acts = db.q("SELECT * FROM agent_activity " + ("WHERE requirement_id=? " if req_id else "") + "ORDER BY id DESC LIMIT 200", (req_id,) if req_id else ())
    allacts = db.q("SELECT agent, action, COUNT(*) n FROM agent_activity " + ("WHERE requirement_id=? " if req_id else "") + "GROUP BY agent, action", (req_id,) if req_id else ())
    cnt = {(a["agent"], a["action"]): a["n"] for a in allacts}
    evals = db.q("SELECT e.* FROM resume_evaluations e " + ("WHERE e.requirement_id=? " if req_id else ""), (req_id,) if req_id else ())
    rej = Counter()
    for c in cands:
        if c["status"] == "rejected":
            a = c["joe_assessment"] or {}
            if a.get("missing"):
                rej["Missing " + ", ".join(a["missing"][:2])] += 1
            else:
                rej["Low overall match"] += 1
    agents = {
        "MARK": {"searches_logged": sum(searches.values()), "channels_used": len([c for c in channels if c["logged_searches"]]),
                 "companies_mapped": len(companies), "profiles_sourced": len(uniq), "refinements": cnt.get(("MARK", "search_refined"), 0),
                 "plans": cnt.get(("MARK", "search_plan_proposed"), 0)},
        "JOE": {"profiles_evaluated": len({(e["requirement_id"], e["candidate_id"]) for e in evals}), "assessments": len(evals),
                "avg_score": round(sum(e["total"] for e in evals) / len(evals), 1) if evals else None,
                "shortlisted": sum(1 for c in cands if c["status"] == "shortlisted"),
                "challenges": cnt.get(("JOE", "challenge"), 0) + cnt.get(("MARK", "challenge"), 0),
                "rejection_reasons": [{"reason": k, "count": v} for k, v in rej.most_common(6) if v]},
        "log": acts[:80],
    }
    connectors = db.q("SELECT * FROM connector_registry ORDER BY category, name")
    return {"generated_at": now(), "filters": f, "overview": overview, "requirements": reqs, "candidates": cands,
            "channels": channels, "channel_performance": perf_list, "best_channel": best, "companies": companies,
            "company_distribution": distribution, "skills": skill_intel, "funnel": funnel, "agents": agents,
            "connectors": connectors, "stages": STAGES}


def snapshot(db, requirement_id=None):
    s = state(db, {"requirement": requirement_id} if requirement_id else {})
    db.insert("recruitment_analytics", {"requirement_id": requirement_id, "snapshot": {"overview": s["overview"], "funnel": s["funnel"],
                                        "channels": s["channel_performance"]}, "at": now()}, audit=False)
    return s
