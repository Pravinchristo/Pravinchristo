"""MARK: search strings, company mapping, channel memory and the sourcing plan."""
import re
from collections import Counter

from . import intake
from . import skills as sk
from .db import new_id, norm_name, now

OPEN_TO_WORK = ['"open to work"', '"#opentowork"', '"actively looking"', '"seeking new opportunities"', '"looking for new opportunities"']
IMMEDIATE = ['"immediate joiner"', '"immediately available"', '"serving notice"', '"last working day"', '"notice period: 15 days"', '"available to join"']
NOT_JOBS = '-job -jobs -hiring -"we are hiring" -recruiter'


def _q(term):
    return f'"{term}"' if re.search(r"[\s./#+-]", term) else term


def _or(terms, cap=6):
    terms = list(dict.fromkeys(t for t in terms if t))[:cap]
    if not terms:
        return ""
    return terms[0] if len(terms) == 1 and " " not in terms[0] else "(" + " OR ".join(_q(t) for t in terms) + ")"


def _loc(req):
    locs = [l.strip() for l in re.split(r",|/|\bor\b", req.get("location") or "") if l.strip() and l.strip().lower() not in ("remote", "any", "india")]
    alias = {"bengaluru": ["Bengaluru", "Bangalore"], "bangalore": ["Bengaluru", "Bangalore"], "gurugram": ["Gurugram", "Gurgaon"], "gurgaon": ["Gurugram", "Gurgaon"]}
    out = []
    for l in locs:
        out += alias.get(l.lower(), [l])
    return list(dict.fromkeys(out))


def titles_for(req, lib):
    fam = lib["families"].get(req.get("job_family") or "", {})
    t = [req["title"]] if req.get("title") else []
    base = re.sub(r"(?i)\b(senior|sr\.?|lead|principal|staff|junior|jr\.?)\s+", "", req.get("title") or "").strip()
    if base and base not in t:
        t.append(base)
    return list(dict.fromkeys(t + fam.get("titles", []))), fam.get("alternate_designations", [])


def booleans(req, lib, companies=None):
    mand = req.get("mandatory_skills") or []
    pref = req.get("preferred_skills") or []
    trans = req.get("transferable_skills") or []
    excl = req.get("excluded_companies") or []
    titles, alt = titles_for(req, lib)
    groups = [_or(sk.aliases(s, lib), 5) for s in mand]
    t_or = _or(titles, 5)
    loc = _or(_loc(req), 4)
    excl_s = " ".join(f"NOT {_q(c)}" for c in excl)
    core = groups[:2]
    out = {
        "broad": " AND ".join(x for x in [t_or, _or([a for s in mand[:3] for a in sk.aliases(s, lib)[:2]], 6)] if x),
        "narrow": " AND ".join(x for x in [t_or] + groups + [loc] if x),
        "skill_based": " AND ".join(groups) if groups else "",
        "designation_based": " AND ".join(x for x in [_or(titles + alt, 10)] + core[:1] if x),
        "company_specific": {},
        "immediate_joiner": " AND ".join(x for x in [t_or] + core + [_or(IMMEDIATE, 6)] if x),
        "open_to_work": " AND ".join(x for x in [t_or] + core + [_or(OPEN_TO_WORK, 5)] if x),
        "alternative_skill": "",
        "xray": {},
        "github": {},
    }
    if excl_s:
        for k in ("broad", "narrow", "skill_based", "designation_based", "immediate_joiner", "open_to_work"):
            if out[k]:
                out[k] += " " + excl_s
    for c in (companies or [])[:10]:
        out["company_specific"][c] = " AND ".join(x for x in [t_or, core[0] if core else "", _q(c)] if x)
    alt_skills = trans + [e for s in mand for e in lib["skills"].get(s, {}).get("equivalents", [])]
    if alt_skills:
        out["alternative_skill"] = " AND ".join(x for x in [_or(titles + alt, 8), _or(alt_skills, 8)] if x)
    sk_terms = " ".join(_or(sk.aliases(s, lib), 3) for s in mand[:3])
    loc_x = _or(_loc(req), 3)
    out["xray"] = {
        "linkedin": f'site:linkedin.com/in {_or(titles, 4)} {sk_terms} {loc_x} {NOT_JOBS}'.replace("  ", " ").strip(),
        "linkedin_open_to_work": f'site:linkedin.com/in {_or(titles, 3)} {sk_terms} {loc_x} ("open to work" OR "#opentowork")'.strip(),
        "github": f'site:github.com {sk_terms} {loc_x} -topic -issues -pull'.strip(),
        "stackoverflow": f'site:stackoverflow.com/users {loc_x} {sk_terms}'.strip(),
        "resume_pages": f'(intitle:resume OR intitle:cv OR inurl:resume) {sk_terms} {loc_x} -job -jobs -template -sample'.strip(),
        "speakers": f'{sk_terms} (speaker OR "talk by" OR meetup) {loc_x}'.strip(),
    }
    fam = lib["families"].get(req.get("job_family") or "", {})
    gh = fam.get("github", {})
    locs = _loc(req)
    out["github"] = {
        "user_search": [f"language:{lang} location:{(locs[0] if locs else 'India').replace(' ', '-')} followers:>5 repos:>5" for lang in gh.get("languages", ["Python"])[:3]],
        "topics": [f"topic:{t} stars:>20" for t in gh.get("topics", [])[:5]],
        "method": "Find active repositories on the topics, then look at their contributors' profiles for location and employer. GitHub shows code evidence only; employment, experience and availability must be verified elsewhere.",
    }
    return out


def map_companies(db, req, lib):
    """Rank companies by overlap with the requirement's skills (relevance, not size)."""
    mand = set(req.get("mandatory_skills") or [])
    pref = set(req.get("preferred_skills") or []) | set(req.get("transferable_skills") or [])
    excl = {norm_name(c) for c in (req.get("excluded_companies") or [])}
    targets = {norm_name(c) for c in (req.get("target_companies") or [])}
    domain = (req.get("domain") or "").lower()
    for t in req.get("target_companies") or []:  # recruiter-named targets join the database, unverified
        n = norm_name(t)
        if n and not db.one("SELECT id FROM target_companies WHERE name_norm=?", (n,)):
            db.insert("target_companies", {"id": new_id("CO"), "name": t, "name_norm": n, "category": "Unclassified",
                                           "industry": None, "business_model": None, "tech_ecosystem": [],
                                           "source": "recruiter target", "verified": 0, "research_date": now()[:10],
                                           "created_at": now(), "updated_at": now()}, actor="MARK")
    rows = []
    titles, alt = titles_for(req, lib)
    for c in db.q("SELECT * FROM target_companies"):
        if c["name_norm"] in excl:
            continue
        tech = set(c["tech_ecosystem"] or [])
        m_hit, p_hit = mand & tech, pref & tech
        rel = (len(m_hit) / len(mand) * 70 if mand else 0) + (min(len(p_hit), 3) / 3 * 15)
        if domain and domain != "none" and c.get("industry") and any(d.strip() and d.strip() in c["industry"].lower() for d in domain.split(",")):
            rel += 10
        if c["name_norm"] in targets:
            rel += 25
        if rel < 25:
            continue
        pri = "P1" if rel >= 70 else "P2" if rel >= 45 else "P3"
        rows.append({"company_id": c["id"], "name": c["name"], "category": c["category"], "relevance": round(rel, 1),
                     "priority": pri, "matched_skills": sorted(m_hit | p_hit), "verified": c["verified"], "source": c["source"]})
    rows.sort(key=lambda r: -r["relevance"])
    for r in rows:
        db.conn.execute("""INSERT INTO company_talent_maps (requirement_id, company_id, relevance, priority, relevant_titles, matched_skills, talent_pool_note, source, research_date)
                           VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(requirement_id, company_id) DO UPDATE SET relevance=excluded.relevance, priority=excluded.priority,
                           matched_skills=excluded.matched_skills, research_date=excluded.research_date""",
                        (req["id"], r["company_id"], r["relevance"], r["priority"], db._enc("relevant_titles", (titles + alt)[:6]),
                         db._enc("matched_skills", r["matched_skills"]), "Skill overlap with the company's known stack; candidate count comes from sourced records.",
                         r["source"], now()[:10]))
    db.conn.commit()
    return rows


def channel_memory(db, job_family=None):
    """Saved channels with what worked before for this job family."""
    chans = db.q("SELECT * FROM sourcing_channels ORDER BY approved DESC, name")
    for c in chans:
        mem = db.q("SELECT * FROM channel_memory WHERE channel_id=? ORDER BY created_at DESC", (c["id"],))
        c["memory_entries"] = len(mem)
        c["family_memory"] = [m for m in mem if job_family and m["job_family"] == job_family][:3]
    return chans


def confirm_channels(db, req, channel_ids, actor="recruiter"):
    """Recruiter-approved channel selection for this campaign. Saved to memory; nothing removed."""
    for cid in channel_ids:
        c = db.one("SELECT * FROM sourcing_channels WHERE id=?", (cid,))
        if not c:
            raise KeyError(cid)
        if not c["approved"]:
            db.update_record("sourcing_channels", {"id": cid}, {"approved": 1}, actor=actor)
    intake = req["intake"]
    intake["channels"] = channel_ids
    db.update_record("requirements", {"id": req["id"]}, {"intake": intake}, actor=actor)
    db.log("MARK", "channels_confirmed", {"channels": [db.one("SELECT name FROM sourcing_channels WHERE id=?", (c,))["name"] for c in channel_ids]}, req["id"])


def build_plan(db, req):
    lib = sk.library(db)
    companies = map_companies(db, req, lib)
    named = req.get("target_companies") or []
    top = list(dict.fromkeys(named + [c["name"] for c in companies[:10]]))
    b = booleans(req, lib, top)
    intel = sk.intelligence(req.get("mandatory_skills") or [], req.get("preferred_skills") or [], req.get("job_family"), lib)
    chan_ids = req["intake"].get("channels") or []
    chans = [db.one("SELECT * FROM sourcing_channels WHERE id=?", (c,)) for c in chan_ids]
    connectors = {c["name"]: c for c in db.q("SELECT * FROM connector_registry")}
    steps = []
    for c in chans:
        if not c:
            continue
        string = {"Google X-Ray": b["xray"]["linkedin"], "GitHub": "; ".join(b["github"]["user_search"]),
                  "Stack Overflow": b["xray"]["stackoverflow"], "Google Search": b["xray"]["speakers"]}.get(c["name"], b["narrow"])
        how = "manual (recruiter runs it and logs results)" if (c["manual_only"] or not c["connected"]) else "connected (MARK can run it)"
        steps.append({"channel": c["name"], "channel_id": c["id"], "execution": how, "connected": bool(c["connected"]),
                      "string": string, "filters_to_check": c["filters"],
                      "note": "Availability filters (Open to Work, notice period) depend on the platform and your account; record what you actually saw."})
    missing = [n for n, c in connectors.items() if c["category"] == "Candidate sourcing" and c["status"] != "connected"]
    plan = {
        "requirement": {k: req.get(k) for k in ("id", "title", "exp_min", "exp_max", "location", "work_mode", "notice_max_days",
                                                "immediate_joiner_pref", "open_to_work_pref", "domain", "profiles_required", "salary_budget")},
        "skills": {"mandatory": req.get("mandatory_skills"), "critical": req.get("critical_skills") or req.get("mandatory_skills"),
                   "preferred": req.get("preferred_skills"), "transferable": req.get("transferable_skills"), "intelligence": intel},
        "booleans": b,
        "target_companies": companies[:15],
        "channels": steps,
        "warnings": intake.market_warnings(req, lib),
        "connector_gaps": missing,
        "joe_scoring": req.get("weights") or "default 100-point model",
        "assumptions": ["Company tech stacks are seed knowledge until verified.", "No channel is marked as searched until a search run is logged."],
    }
    ver = (db.one("SELECT MAX(version) v FROM search_strategies WHERE requirement_id=?", (req["id"],)) or {}).get("v") or 0
    db.conn.execute("UPDATE search_strategies SET status='superseded' WHERE requirement_id=? AND status='proposed'", (req["id"],))
    sid = db.insert("search_strategies", {"requirement_id": req["id"], "version": ver + 1, "payload": plan, "status": "proposed", "created_at": now()}, actor="MARK")
    if req["status"] in ("intake", "plan_pending"):
        db.update_record("requirements", {"id": req["id"]}, {"status": "plan_pending"}, actor="MARK")
    db.log("MARK", "search_plan_proposed", {"version": ver + 1, "companies": len(companies), "channels": len(steps)}, req["id"])
    plan["strategy_id"], plan["version"] = sid, ver + 1
    return plan


def approve_plan(db, req, actor="recruiter"):
    s = db.one("SELECT * FROM search_strategies WHERE requirement_id=? AND status='proposed' ORDER BY version DESC", (req["id"],))
    if not s:
        raise ValueError("No proposed plan to approve.")
    db.update_record("search_strategies", {"id": s["id"]}, {"status": "approved", "decided_at": now()}, actor=actor)
    db.update_record("requirements", {"id": req["id"]}, {"status": "hunting"}, actor=actor)
    lib = sk.library(db)
    titles, alt = titles_for(req, lib)
    for step in s["payload"]["channels"]:  # store approved strategies per channel in shared memory
        db.insert("channel_memory", {"channel_id": step["channel_id"], "requirement_id": req["id"], "job_family": req.get("job_family"),
                                     "search_methodology": step["execution"], "boolean_strings": {"primary": step["string"], "narrow": s["payload"]["booleans"]["narrow"]},
                                     "filters": step["filters_to_check"], "target_designations": titles + alt,
                                     "skill_combinations": [req.get("mandatory_skills"), req.get("transferable_skills")],
                                     "approved_by": actor, "created_at": now()}, actor=actor)
        db.conn.execute("UPDATE sourcing_channels SET date_last_used=? WHERE id=?", (now(), step["channel_id"]))
    db.conn.commit()
    db.log("MARK", "search_plan_approved", {"version": s["version"], "by": actor}, req["id"])
    return s


def log_search(db, req_id, channel_id, query, results_count, evidence, executed_by="recruiter"):
    """The only way a channel counts as 'searched': a logged run with evidence (URL, screenshot path, export file)."""
    if not evidence:
        raise ValueError("A search run needs evidence (results URL, export file or note of what was seen).")
    db.insert("search_runs", {"requirement_id": req_id, "channel_id": channel_id, "query": query, "executed_by": executed_by,
                              "results_count": results_count, "evidence": evidence, "at": now()}, actor=executed_by)
    db.log("MARK", "search_run_logged", {"channel_id": channel_id, "results": results_count, "by": executed_by}, req_id)


def refine(db, req):
    """MARK reads JOE's evaluations and proposes changes to the hunt."""
    evals = db.q("""SELECT e.*, p.source_channel, c.current_company FROM resume_evaluations e
                    JOIN pipeline p ON p.requirement_id=e.requirement_id AND p.candidate_id=e.candidate_id
                    JOIN candidates c ON c.id=e.candidate_id WHERE e.requirement_id=?
                    AND e.id IN (SELECT MAX(id) FROM resume_evaluations GROUP BY requirement_id, candidate_id)""", (req["id"],))
    if not evals:
        return {"refinements": [], "note": "No evaluations yet; nothing to learn from."}
    n = len(evals)
    gaps = Counter(g for e in evals for g in (e["missing_skills"] or []))
    strong = [e for e in evals if e["total"] >= 70]
    out = []
    for skill, cnt in gaps.most_common(3):
        if cnt / n >= 0.5:
            out.append({"type": "skill_gap", "text": f"{cnt}/{n} evaluated profiles lack evidence of {skill}.",
                        "action": f"Add a skill-led string for {skill} (and its equivalents) or ask whether {skill} can move to preferred."})
    comp = Counter(e["current_company"] for e in strong if e["current_company"])
    for c, cnt in comp.most_common(3):
        out.append({"type": "company", "text": f"{cnt} strong profile(s) from {c}.", "action": f"Raise {c} to P1 and search its alumni (past company filter)."})
    by_ch = {}
    for e in evals:
        d = by_ch.setdefault(e["source_channel"] or "unknown", [0, 0])
        d[0] += 1
        d[1] += e["total"] >= 55
    for ch, (tot, rel) in by_ch.items():
        if tot >= 3 and rel / tot < 0.25:
            out.append({"type": "channel", "text": f"{ch}: only {rel}/{tot} relevant.", "action": f"Narrow the {ch} string or shift effort to better channels."})
    low_ev = sum(1 for e in evals if any(v.get("level") == "mentioned" for v in (e["skill_evidence"] or {}).values()))
    if low_ev / n >= 0.5:
        out.append({"type": "evidence", "text": "Most profiles list skills without project evidence.", "action": "Add project terms to strings (e.g. 'implemented', 'migrated', 'production')."})
    db.log("MARK", "search_refined", {"refinements": len(out), "from_evaluations": n}, req["id"])
    return {"refinements": out, "evaluated": n}
