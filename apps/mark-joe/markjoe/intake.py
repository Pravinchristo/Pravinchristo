"""MARK's Intelligent Mode: reads the JD, finds what is missing or contradictory,
and asks one essential question at a time. Nothing already in the JD is asked again."""
import re

from . import skills as sk
from .db import new_id, now

CITIES = ["Bengaluru", "Bangalore", "Hyderabad", "Chennai", "Pune", "Mumbai", "Navi Mumbai", "Gurugram", "Gurgaon",
          "Noida", "Delhi", "New Delhi", "Kolkata", "Ahmedabad", "Kochi", "Coimbatore", "Trivandrum", "Thiruvananthapuram",
          "Indore", "Jaipur", "Chandigarh", "Mysore", "Mysuru", "Bhubaneswar", "Nagpur", "Vadodara",
          "London", "Singapore", "Dubai", "New York", "San Francisco", "Seattle", "Austin", "Toronto", "Sydney"]
DOMAINS = ["banking", "BFSI", "insurance", "fintech", "payments", "capital markets", "healthcare", "life sciences",
           "pharma", "retail", "e-commerce", "telecom", "OTT", "media", "gaming", "automotive", "manufacturing",
           "energy", "logistics", "supply chain", "travel", "edtech", "adtech", "cybersecurity", "semiconductor"]
EDU = [r"B\.?\s?E\b", r"B\.?\s?Tech", r"M\.?\s?Tech", r"MCA", r"BCA", r"M\.?\s?S\b", r"MBA", r"Ph\.?\s?D",
       r"Bachelor'?s?(?: degree)?(?: in [A-Za-z ]+)?", r"Master'?s?(?: degree)?(?: in [A-Za-z ]+)?"]

MAND_HEAD = r"(must[- ]have|mandatory|required skills|requirements|key skills|essential|primary skills|technical skills|what you need|qualifications)"
PREF_HEAD = r"(good[- ]to[- ]have|nice[- ]to[- ]have|preferred|desirable|bonus|plus points|secondary skills|added advantage)"

# Base questions, in the order MARK asks them. `essential` ones must be answered or skipped before a plan.
BASE_QUESTIONS = [
    ("title", True, "What is the job title for this requirement?", "The title drives the designation Boolean and the alternate titles MARK hunts."),
    ("mandatory_skills", True, "Which technical skills are mandatory? (comma-separated)", "Only mandatory skills gate a shortlist; everything else is scored as a plus."),
    ("experience", True, "What experience range do you want? (e.g. 5-8 years)", "Experience sets seniority filters and the experience-alignment score."),
    ("location", True, "Which location(s)? Is relocation acceptable?", "Location filters every channel; relocation widens the pool."),
    ("work_mode", True, "Work mode: onsite, hybrid or remote?", "Remote roles let MARK search other cities; onsite roles don't."),
    ("notice_period", True, "What is the maximum notice period you can accept? (e.g. immediate, 30, 60, 90 days)", "Notice period is the most common reason a good profile drops out late."),
    ("profiles_required", True, "How many profiles do you need in the shortlist?", "It sets how wide MARK hunts before handing over to JOE."),
    ("preferred_skills", False, "Any preferred (good-to-have) skills?", "Preferred skills add points but never block a candidate."),
    ("salary_budget", False, "What is the salary budget (e.g. 25-35 LPA)?", "Budget decides which company tiers are realistic to approach."),
    ("immediate_joiner", False, "Do you need immediate joiners: required, preferred, or no preference?", "MARK adds an immediate-joiner Boolean and only marks someone immediate with evidence."),
    ("open_to_work", False, "Should MARK prioritise Open to Work candidates: required, preferred, or no preference?", "Open to Work is self-declared and not visible on every channel; it is used as a signal, not a filter, unless you say so."),
    ("domain", False, "Any domain requirement (e.g. BFSI, healthcare, retail)? Say 'none' if not.", "Domain shifts target companies and the domain score."),
    ("target_companies", False, "Any target companies to hunt from? (comma-separated, or 'none')", "Named targets get their own company-specific Booleans."),
    ("excluded_companies", False, "Any companies to exclude (clients, non-solicit, current employer)?", "MARK removes them from all strings and company maps."),
    ("education", False, "Any education requirement? Say 'none' if not.", "Strict education rules can exclude strong self-taught engineers; say so only if it is truly required."),
]
FIELD_FOR = {"experience": ("exp_min", "exp_max"), "notice_period": ("notice_max_days",), "immediate_joiner": ("immediate_joiner_pref",),
             "open_to_work": ("open_to_work_pref",)}
SKIP = re.compile(r"^\s*(skip|none|n/?a|no|not required|no preference|any|nil|-)\s*\.?\s*$", re.I)


def _lines(text):
    return [l.strip(" \t•*-–·>") for l in (text or "").splitlines()]


def _field_line(text, labels):
    m = re.search(r"(?im)^\W*(?:" + labels + r")\s*[:\-–]\s*(.+)$", text or "")
    return m.group(1).strip() if m else None


def parse_experience(t):
    if not t:
        return None, None
    t = t.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years|yrs|year|y\b)?", t)
    if m and ("year" in t or "yr" in t or re.fullmatch(r"\s*[\d.]+\s*(?:-|to|–)\s*[\d.]+\s*", t)):
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(?:minimum|min\.?|at least|over)?\s*(\d+(?:\.\d+)?)\s*(?:\+|plus)\s*(?:years|yrs)?", t)
    if m:
        return float(m.group(1)), None
    m = re.search(r"(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(?:years|yrs)", t)
    if m:
        return float(m.group(1)), None
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)?\s*", t)
    if m:
        return float(m.group(1)), None
    return None, None


def parse_notice(t):
    if not t:
        return None
    t = t.lower()
    if "immediate" in t:
        return 0
    m = re.search(r"(\d+)\s*(day|days|d\b)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(month|months)", t)
    if m:
        return int(m.group(1)) * 30
    m = re.fullmatch(r"\s*(\d+)\s*", t)
    return int(m.group(1)) if m else None


def parse_pref(t):
    t = (t or "").lower()
    if any(w in t for w in ("required", "must", "mandatory", "only", "compulsory", "yes")):
        return "required"
    if any(w in t for w in ("prefer", "plus", "nice", "good to")):
        return "preferred"
    return "no preference"


def split_list(t):
    parts = re.split(r",|;|/(?!\s*cd)|\band\b|\bor\b|\n", t or "", flags=re.I)
    return [p.strip(" .") for p in parts if p.strip(" .") and not SKIP.match(p)]


def parse_jd(jd, lib):
    """Extract every field the JD already answers, plus skill sections."""
    out = {}
    text = jd or ""
    low = text.lower()
    title = _field_line(text, r"job title|title|role|position|designation")
    if not title:
        first = next((l for l in _lines(text) if l), "")
        if first and len(first) <= 80 and not re.search(r"(?i)we are|about|looking for|description", first):
            title = first
        else:
            m = re.search(r"(?i)(?:hiring|looking for|seeking)\s+(?:an?\s+)?([A-Z][A-Za-z/ ]{3,60}?)(?:\s+(?:with|to|who|in|for)\b|[.,\n])", text)
            title = m.group(1).strip() if m else None
    if title:
        out["title"] = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()

    exp_src = _field_line(text, r"experience|exp|years of experience") or text
    mn, mx = parse_experience(exp_src)
    if mn is None and exp_src is not text:
        mn, mx = parse_experience(text)
    if mn is not None:
        out["exp_min"], out["exp_max"] = mn, mx

    loc = _field_line(text, r"location|locations|job location|work location|based in")
    if not loc:
        found = [c for c in CITIES if re.search(r"(?i)\b" + re.escape(c) + r"\b", text)]
        loc = ", ".join(dict.fromkeys(found)) if found else None
    if loc:
        out["location"] = loc

    modes = [m for m in ("remote", "hybrid", "onsite", "on-site", "work from office", "wfo", "in-office") if m in low]
    if modes:
        mode = "remote" if "remote" in modes else "hybrid" if "hybrid" in modes else "onsite"
        out["work_mode"] = mode
        if "remote" in modes and any(m in modes for m in ("onsite", "on-site", "work from office", "wfo", "in-office")):
            out["_mode_conflict"] = True

    sal = _field_line(text, r"salary|budget|ctc|compensation|package|pay range")
    if not sal:
        m = re.search(r"(?i)(?:₹|inr|rs\.?|\$|usd)?\s*\d+(?:\.\d+)?\s*(?:-|to|–)\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?|l\b|k\b|cr|usd|inr)", text)
        sal = m.group(0).strip() if m else None
    if sal:
        out["salary_budget"] = sal

    nl = _field_line(text, r"notice period|notice")
    m = re.search(r"(?i)notice(?: period)?[^.\n]{0,40}?(\d+)\s*(days|months)", text)
    if nl and parse_notice(nl) is not None:
        out["notice_max_days"] = parse_notice(nl)
    elif m:
        out["notice_max_days"] = parse_notice(m.group(1) + " " + m.group(2))
    if re.search(r"(?i)immediate joiners?\s*(only|required|mandatory)|only immediate", text):
        out["immediate_joiner_pref"] = "required"
        out.setdefault("notice_max_days", 0)
    elif re.search(r"(?i)immediate joiners?|immediate to \d+ days|can join immediately", text):
        out["immediate_joiner_pref"] = "preferred"
        m2 = re.search(r"(?i)immediate to (\d+) days", text)
        if m2:
            out.setdefault("notice_max_days", int(m2.group(1)))
    if re.search(r"(?i)open to work", text):
        out["open_to_work_pref"] = "preferred"

    doms = [d for d in DOMAINS if re.search(r"(?i)\b" + re.escape(d) + r"\b", text)]
    if doms:
        out["domain"] = ", ".join(doms)
    edu = [re.search(p, text).group(0).strip() for p in EDU if re.search(p, text)]
    if edu:
        out["education"] = ", ".join(dict.fromkeys(edu))
    m = re.search(r"(?i)(\d+)\s*(?:profiles|positions|openings|candidates|resumes|hires)\b", text)
    if m:
        out["profiles_required"] = int(m.group(1))
    m = re.search(r"(?im)(?:target companies|preferably from|candidates from|source from|companies like)\s*[:\-]?\s*(.+)$", text)
    if m:
        out["target_companies"] = split_list(m.group(1))
    m = re.search(r"(?im)(?:exclude(?:d)? companies|exclude|excluding|do not (?:source|hire) from|no candidates from|non[- ]solicit)\s*[:\-]?\s*(.+)$", text)
    if m:
        out["excluded_companies"] = split_list(m.group(1))

    # skill sections
    mand, pref, current = [], [], None
    sectioned = False
    for line in (text or "").splitlines():
        l = line.strip()
        if re.search(r"(?i)^\W*" + PREF_HEAD, l) or re.search(r"(?i)\b" + PREF_HEAD + r"\s*:", l):
            current, sectioned = "pref", True
        elif re.search(r"(?i)^\W*" + MAND_HEAD, l) or re.search(r"(?i)\b" + MAND_HEAD + r"\s*:", l):
            current, sectioned = "mand", True
        found = sk.find_skills(l, lib)
        if re.search(r"(?i)\b(good|nice) to have\b|\bpreferred\b|\bis a plus\b|\bplus\b|\bdesirable\b", l) and current != "mand":
            pref += found
        elif re.search(r"(?i)\b(good|nice) to have\b|\bis a plus\b|\bdesirable\b", l):
            pref += found
        elif current == "pref":
            pref += found
        else:
            mand += found
    mand = list(dict.fromkeys(mand))
    pref = [s for s in dict.fromkeys(pref) if s not in mand]
    out["_found_skills"] = list(dict.fromkeys(mand + pref))
    out["_sectioned"] = sectioned
    if mand:
        out["mandatory_skills"] = mand
    if pref:
        out["preferred_skills"] = pref
    return out


def _answered(req, key):
    a = req["intake"].get("answers", {})
    if key in a or key in req["intake"].get("skipped", []):
        return True
    if key in FIELD_FOR:
        return req.get(FIELD_FOR[key][0]) is not None
    v = req.get(key)
    if key == "mandatory_skills" and not req["intake"].get("skills_confirmed"):
        return False
    return v not in (None, "", [], 0) if key != "profiles_required" else bool(v)


def market_warnings(req, lib):
    """Contradictions and market-limiting choices. Each warning says why it matters."""
    w = []
    title = (req.get("title") or "").lower()
    mn, mx = req.get("exp_min"), req.get("exp_max")
    mand = req.get("mandatory_skills") or []
    if mn is not None and mx is not None and mn > mx:
        w.append({"type": "contradiction", "text": f"Experience minimum ({mn:g}) is higher than the maximum ({mx:g}).", "suggest": "Swap or correct the range."})
    if mn is not None and re.search(r"\b(junior|associate|fresher|trainee|graduate)\b", title) and mn >= 5:
        w.append({"type": "contradiction", "text": f"Title says junior but asks for {mn:g}+ years.", "suggest": "Retitle as mid/senior or lower the range."})
    if mx is not None and re.search(r"\b(senior|sr\.?|lead|principal|staff)\b", title) and mx < 4:
        w.append({"type": "contradiction", "text": f"Title says senior/lead but caps experience at {mx:g} years.", "suggest": "Raise the cap or retitle."})
    if mx is not None and re.search(r"\b(architect|head|director)\b", title) and mx < 8:
        w.append({"type": "contradiction", "text": f"Architect/leadership title with at most {mx:g} years is rare.", "suggest": "Consider 8+ years, or a Senior Engineer title."})
    if req.get("intake", {}).get("mode_conflict"):
        w.append({"type": "contradiction", "text": "The JD mentions both remote and work-from-office.", "suggest": "Confirm one work mode."})
    clouds = [s for s in mand if s in ("AWS", "Azure", "GCP")]
    if len(clouds) >= 2:
        w.append({"type": "market", "text": f"{' and '.join(clouds)} are all mandatory; few profiles show production depth in more than one cloud.", "suggest": "Make it 'any one of' and score the others as preferred."})
    for i, a in enumerate(mand):
        for b in mand[i + 1:]:
            if b in lib["skills"].get(a, {}).get("equivalents", []) and not ({a, b} <= {"AWS", "Azure", "GCP"}):
                w.append({"type": "market", "text": f"{a} and {b} are alternatives to each other but both are mandatory.", "suggest": f"Accept either {a} or {b}."})
    if len(mand) > 7:
        w.append({"type": "market", "text": f"{len(mand)} mandatory skills: very few profiles evidence all of them.", "suggest": "Keep 4-6 true must-haves and move the rest to preferred."})
    low = [s for s in mand if lib["skills"].get(s, {}).get("market_availability") == "low"]
    if len(low) >= 2:
        w.append({"type": "market", "text": f"Several scarce skills are mandatory ({', '.join(low)}). The pool will be small.", "suggest": "Make one of them preferred, or accept transferable equivalents."})
    if req.get("immediate_joiner_pref") == "required" and (mn or 0) >= 10:
        w.append({"type": "market", "text": "Immediate joiners only, at 10+ years: most senior people serve 60-90 days' notice.", "suggest": "Accept up to 30-60 days, or buy-out."})
    elif req.get("notice_max_days") is not None and req["notice_max_days"] <= 30 and (mn or 0) >= 8:
        w.append({"type": "market", "text": f"Notice cap of {req['notice_max_days']} days at {mn:g}+ years will exclude many passive candidates.", "suggest": "Consider 60 days or a buy-out option."})
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakh)", (req.get("salary_budget") or "").lower())
    if m and mn and float(m.group(2)) < mn * 1.8:
        w.append({"type": "market", "text": f"Budget up to {m.group(2)} LPA may be low for {mn:g}+ years (MARK heuristic, not market data).", "suggest": "Check with compensation data before launch."})
    return w


def create_requirement(db, jd_text, actor="recruiter"):
    lib = sk.library(db)
    p = parse_jd(jd_text, lib)
    fam = sk.detect_family((p.get("title") or "") + " " + jd_text, p.get("_found_skills", []), lib)
    rid = new_id("REQ")
    rec = {"id": rid, "title": p.get("title"), "jd_text": jd_text, "job_family": fam,
           "exp_min": p.get("exp_min"), "exp_max": p.get("exp_max"), "location": p.get("location"),
           "work_mode": p.get("work_mode"), "salary_budget": p.get("salary_budget"),
           "notice_max_days": p.get("notice_max_days"), "immediate_joiner_pref": p.get("immediate_joiner_pref"),
           "open_to_work_pref": p.get("open_to_work_pref"), "domain": p.get("domain"), "education": p.get("education"),
           "profiles_required": p.get("profiles_required"), "target_companies": p.get("target_companies", []),
           "excluded_companies": p.get("excluded_companies", []), "mandatory_skills": p.get("mandatory_skills", []),
           "preferred_skills": p.get("preferred_skills", []), "transferable_skills": [], "critical_skills": [],
           "intake": {"answers": {}, "skipped": [], "asked": [], "found_skills": p.get("_found_skills", []),
                      "sectioned": p.get("_sectioned", False),
                      "skills_confirmed": bool(p.get("_sectioned") and p.get("mandatory_skills")), "mode_conflict": bool(p.get("_mode_conflict")),
                      "from_jd": sorted(k for k in p if not k.startswith("_")), "notes": []},
           "status": "intake", "created_at": now(), "updated_at": now()}
    db.insert("requirements", rec, actor=actor)
    db.log("MARK", "intelligent_mode_started", {"from_jd": rec["intake"]["from_jd"], "family": fam}, rid)
    return get(db, rid)


def get(db, rid):
    r = db.one("SELECT * FROM requirements WHERE id=?", (rid,))
    if r is None:
        raise KeyError(rid)
    return r


def pending_questions(req, lib):
    qs = []
    for key, essential, prompt, why in BASE_QUESTIONS:
        if _answered(req, key):
            continue
        if key == "mandatory_skills" and req["intake"].get("found_skills"):
            found = req.get("mandatory_skills") or req["intake"]["found_skills"]
            pref = req.get("preferred_skills") or []
            prompt = (f"From the JD I read these as mandatory: {', '.join(found)}"
                      + (f"; and as preferred: {', '.join(pref)}" if pref else "")
                      + ". Reply 'yes' to confirm, or list the true mandatory skills.")
            why = "Only mandatory skills gate the shortlist, so it is worth confirming what the JD lists as must-haves."
        qs.append({"key": key, "essential": essential, "question": prompt, "why": why})
    fam = lib["families"].get(req.get("job_family") or "")
    if fam:
        mand = req.get("mandatory_skills") or []
        for f in fam["followups"]:
            if f["key"] in req["intake"]["answers"] or f["key"] in req["intake"]["skipped"]:
                continue
            if f["if_skill"] and f["if_skill"] not in mand:
                continue
            qs.append({"key": f["key"], "essential": False, "question": f["q"], "why": f["why"], "followup": True})
    # order: essentials, then follow-ups (they shape the search), then the rest
    return sorted(qs, key=lambda q: (not q["essential"], not q.get("followup"), 0))


def next_question(db, req):
    lib = sk.library(db)
    qs = pending_questions(req, lib)
    return qs[0] if qs else None


def ready_for_plan(db, req):
    lib = sk.library(db)
    return not any(q["essential"] for q in pending_questions(req, lib))


def _apply_followup(req, key, text, lib):
    """Follow-up answers can relax mandatory skills into preferred/transferable. Never the other way silently."""
    low = text.lower()
    relax = re.search(r"\b(no|not mandatory|optional|can be considered|acceptable|either|any|open|fine|ok)\b", low)
    changes, note = {}, None
    fam = lib["families"].get(req.get("job_family") or "", {})
    f = next((x for x in fam.get("followups", []) if x["key"] == key), None)
    yes = bool(re.match(r"\W*(yes|y\b|mandatory|must|compulsory|required|definitely)", low))
    if f and yes and f.get("on_yes"):
        rl = dict(req["intake"].get("required_levels") or {})
        rl[f["on_yes"]["skill"]] = f["on_yes"]["level"]
        req["intake"]["required_levels"] = rl
        note = f"JOE will require {f['on_yes']['level'].replace('_', '-')} evidence for {f['on_yes']['skill']}."
    elif f and f["if_skill"] and relax and not yes and f.get("on_no") == "keep":
        note = f"{f['if_skill']} stays mandatory; deeper production evidence is not required."
    elif f and f["if_skill"] and relax and not yes:
        s = f["if_skill"]
        mand = [m for m in req["mandatory_skills"] if m != s]
        pref = list(dict.fromkeys(req["preferred_skills"] + [s]))
        trans = list(dict.fromkeys(req["transferable_skills"] + lib["skills"].get(s, {}).get("equivalents", [])))
        changes = {"mandatory_skills": mand, "preferred_skills": pref, "transferable_skills": trans}
        note = f"{s} moved from mandatory to preferred; equivalents accepted as transferable."
    if key == "fu_cloud":
        clouds = [c for c in ("AWS", "Azure", "GCP") if c.lower() in low]
        if re.search(r"\b(any|either|acceptable|all fine|open)\b", low):
            mand = [m for m in req["mandatory_skills"] if m not in ("AWS", "Azure", "GCP")]
            trans = list(dict.fromkeys(req["transferable_skills"] + ["AWS", "Azure", "GCP"]))
            changes = {"mandatory_skills": mand, "transferable_skills": trans}
            note = "Any major cloud accepted; cloud is scored as transferable."
        elif len(clouds) == 1 and clouds[0] not in req["mandatory_skills"]:
            changes = {"mandatory_skills": req["mandatory_skills"] + clouds}
            note = f"{clouds[0]} added as mandatory."
    if key == "fu_arch" and re.search(r"\b(yes|prioriti[sz]e|architecture)\b", low) and not low.startswith("no"):
        w = dict(req.get("weights") or {})
        w.update({"architecture": 15, "hands_on": 10})
        changes = {"weights": w}
        note = "Scoring: architecture weight raised to 15, hands-on lowered to 10."
    return changes, note


def answer(db, rid, text, key=None, actor="recruiter"):
    """Store the recruiter's answer to the pending (or named) question and return the next one."""
    lib = sk.library(db)
    req = get(db, rid)
    q = next((x for x in pending_questions(req, lib) if x["key"] == key), None) if key else next_question(db, req)
    if q is None:
        return req, None, None
    key = q["key"]
    intake = req["intake"]
    intake["asked"].append(key)
    changes, note = {}, None
    t = (text or "").strip()
    is_followup = key.startswith("fu_")
    if (SKIP.match(t) and not is_followup and key not in ("immediate_joiner", "open_to_work", "mandatory_skills", "title")) or (is_followup and t.lower() in ("skip", "-")):
        intake["skipped"].append(key)
        if key == "domain":
            changes["domain"] = "none"
        note = f"{key} left open."
    elif key == "title":
        changes["title"] = t
        fam = sk.detect_family(t + " " + (req["jd_text"] or ""), req["mandatory_skills"], lib)
        if fam:
            changes["job_family"] = fam
    elif key == "mandatory_skills":
        if re.match(r"(?i)^\s*(yes|y|ok|confirm(ed)?|correct|right)\b", t):
            skills = req["mandatory_skills"] or intake.get("found_skills", [])
        else:
            skills = [sk.canonical(s, lib) for s in split_list(t)]
        intake["skills_confirmed"] = True
        changes["mandatory_skills"] = list(dict.fromkeys(skills))
        changes["preferred_skills"] = [s for s in req["preferred_skills"] if s not in skills]
        changes["critical_skills"] = list(dict.fromkeys(skills))
    elif key == "preferred_skills":
        changes["preferred_skills"] = list(dict.fromkeys(req["preferred_skills"] + [sk.canonical(s, lib) for s in split_list(t) if sk.canonical(s, lib) not in req["mandatory_skills"]]))
    elif key == "experience":
        mn, mx = parse_experience(t if re.search(r"(?i)year|yr", t) else t + " years")
        if mn is None:
            return req, q, {"error": "I couldn't read an experience range. Try '5-8 years' or '6+ years'."}
        changes.update(exp_min=mn, exp_max=mx)
    elif key == "notice_period":
        n = parse_notice(t)
        if n is None:
            return req, q, {"error": "I couldn't read a notice period. Try 'immediate', '30 days' or '2 months'."}
        changes["notice_max_days"] = n
    elif key == "profiles_required":
        m = re.search(r"\d+", t)
        if not m:
            return req, q, {"error": "Please give a number of profiles, e.g. 10."}
        changes["profiles_required"] = int(m.group(0))
    elif key == "work_mode":
        low = t.lower()
        changes["work_mode"] = "remote" if "remote" in low else "hybrid" if "hybrid" in low else "onsite"
        intake["mode_conflict"] = False
    elif key in ("immediate_joiner", "open_to_work"):
        changes[FIELD_FOR[key][0]] = parse_pref(t)
    elif key in ("target_companies", "excluded_companies"):
        changes[key] = list(dict.fromkeys((req.get(key) or []) + split_list(t)))
    elif key in ("location", "salary_budget", "domain", "education"):
        changes[key] = t
    else:  # follow-up
        changes, note = _apply_followup(req, key, t, lib)
    intake["answers"][key] = t
    if note:
        intake["notes"].append(note)
    changes["intake"] = intake
    req = db.update_record("requirements", {"id": rid}, changes, actor=actor)
    db.log("MARK", "clarification_recorded", {"question": key, "answer": t, "note": note}, rid)
    return req, next_question(db, req), {"note": note} if note else {}
