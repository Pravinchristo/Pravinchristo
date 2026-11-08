"""JOE: resume evidence extraction, experience maths and the 100-point match model.

A keyword is never proof. Each skill gets the strongest evidence level found in
the resume, with the sentence that shows it:
  mentioned < project < hands_on < architecture / production / leadership
"""
import datetime
import re

from . import skills as sk
from .db import norm_email, norm_name, norm_url, now

DEFAULT_WEIGHTS = {"mandatory": 35, "projects": 20, "hands_on": 15, "architecture": 10,
                   "experience": 5, "domain": 5, "availability": 5, "location": 5}
LEVELS = ["mentioned", "project", "hands_on", "architecture", "production", "leadership"]
LEVEL_CREDIT = {"mentioned": 0.2, "project": 0.6, "hands_on": 0.85, "architecture": 1.0, "production": 1.0, "leadership": 1.0}
CUES = {
    "leadership": r"\b(led|lead(ing)?|managed|mentor(ed|ing)?|headed|team of \d+|guided a team|people manager)\b",
    "production": r"\b(production|prod\b|go-live|went live|deployed|deployment|live traffic|sla|on-call|in prod|released to)\b",
    "architecture": r"\b(architected|architecture|designed the|solution design|system design|designed and|high-level design|hld|lld|reference architecture)\b",
    "hands_on": r"\b(implemented|developed|built|wrote|coded|created|automated|migrated|optimi[sz]ed|engineered|programmed|configured|integrated|tuned|refactored|debugged|won|closed|signed|acquired|landed|opened|generated|grew|achieved|exceeded|sells|sold|selling|drove|drives|driving|owns|owned|ran|runs|pursued|helped|managed|built)\b",
    "project": r"\b(project|worked on|used|using|involved in|exposure|responsible for|participated|client)\b",
}
SENSITIVE = re.compile(r"(?i)^\W*(date of birth|dob|age|gender|sex|marital status|religion|caste|nationality|passport|father'?s name|spouse|photo)\b.*$", re.M)
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE = r"(?:(?P<m{n}>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*[,']?\s*|(?P<mm{n}>\d{{1,2}})[/\-.])?(?P<y{n}>(?:19|20)\d{{2}})"
RANGE = re.compile(DATE.format(n=1) + r"\s*(?:-|–|—|to|till|until)\s*(?:" + DATE.format(n=2) + r"|(?P<present>present|current|now|till date|date|ongoing))", re.I)


def _ym(m, n, today):
    y = m.group(f"y{n}")
    if not y:
        return None
    mon = m.group(f"m{n}")
    mm = m.group(f"mm{n}")
    month = MONTHS.get(mon[:3].lower()) if mon else int(mm) if mm and 1 <= int(mm) <= 12 else 1
    return int(y) * 12 + month - 1


SECTION = re.compile(r"(?im)^[ \t]*(?:#{1,3}[ \t]*)?(experience|work experience|professional experience|employment(?: history)?|work history|"
                     r"education|academics?|academic background|educational qualifications?|qualifications?|certifications?|"
                     r"licenses(?: & | and )certifications|courses|projects|skills|about|summary|profile)[ \t]*:?[ \t]*$")


def parse_roles(text, today=None):
    """Find date ranges and the text block that follows each one (a role or project)."""
    today = today or datetime.date.today()
    tnow = today.year * 12 + today.month - 1
    found = []
    heads = [(h.start(), bool(re.match(r"(?i)educ|academ|qualif|certif|licen|course", h.group(1))))
             for h in SECTION.finditer(text)]
    for m in RANGE.finditer(text):
        sec = [edu for pos, edu in heads if pos <= m.start()]
        if sec and sec[-1]:  # dates under Education / Certifications are not work experience
            continue
        s = _ym(m, 1, today)
        e = tnow if m.group("present") else _ym(m, 2, today)
        if s is None or e is None or e < s or e > tnow + 1:
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        found.append({"start": s, "end": e, "pos": line_start, "header": text[line_start:text.find("\n", m.end()) if text.find("\n", m.end()) != -1 else len(text)].strip()})
    for i, r in enumerate(found):
        nxt = found[i + 1]["pos"] if i + 1 < len(found) else len(text)
        r["block"] = text[r["pos"]:nxt]
        r["months"] = r["end"] - r["start"] + 1
    return found


def merge_months(ranges):
    iv = sorted((r["start"], r["end"]) for r in ranges)
    merged = []
    for s, e in iv:
        if merged and s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def experience(text, today=None):
    roles = parse_roles(text, today)
    merged = merge_months(roles)
    total = sum(e - s + 1 for s, e in merged) / 12 if merged else None
    gaps = []
    for (s1, e1), (s2, e2) in zip(merged, merged[1:]):
        if s2 - e1 - 1 >= 6:
            gaps.append({"months": s2 - e1 - 1, "from": f"{(e1 + 1) // 12}-{(e1 + 1) % 12 + 1:02d}", "to": f"{(s2 - 1) // 12}-{(s2 - 1) % 12 + 1:02d}"})
    stated = re.search(r"(?i)(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:total\s+|overall\s+|professional\s+|it\s+)?experience", text)
    # "Total Experience: 7 years and 5 months" is the source's own sum of the full dated history (profile exports
    # carry it); it beats our own sum when the text we hold is a truncated copy of that history
    m = re.search(r"(?i)total experience\s*[:\-]\s*(\d+)\s*(?:years?|yrs)(?:\s*(?:and\s*)?(\d+)\s*months?)?", text)
    listed = round(int(m.group(1)) + int(m.group(2) or 0) / 12, 1) if m else None
    return {"roles": roles, "total_years": round(total, 1) if total is not None else None,
            "stated_years": float(stated.group(1)) if stated else None, "listed_years": listed, "gaps": gaps}


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]


def skill_evidence(text, skills, lib, roles=None):
    """For each skill: strongest level, all levels seen, evidence sentences, confidence."""
    sents = _sentences(text)
    roles = roles or []
    out = {}
    for s in skills:
        pats = [sk._pattern(a.lower()) for a in sk.aliases(s, lib) if len(a) > 2 or a.isupper()]
        hits = [x for x in sents if any(p.search(" " + x.lower() + " ") for p in pats)]
        if not hits:
            out[s] = {"level": None, "levels": [], "evidence": [], "confidence": "none"}
            continue
        levels, ev = set(), []
        for h in hits:
            low = h.lower()
            is_list = bool(re.match(r"(?i)^\W*(skills|technical skills|technologies|tools|key skills|tech stack|languages|environment)\W*[:\-]", h)) or h.count(",") >= 4 and not re.search(CUES["hands_on"], low)
            lv = "mentioned"
            if not is_list:
                for name in ("leadership", "production", "architecture", "hands_on", "project"):
                    if re.search(CUES[name], low):
                        levels.add(name)
                        lv = name if LEVELS.index(name) > LEVELS.index(lv) else lv
            levels.add(lv)
            ev.append({"level": lv, "text": h[:240]})
        # a skill named inside a dated role (outside a bare skills list) counts as used in that project
        LIST_LINE = re.compile(r"(?i)\b(skills|technologies|tools|tech stack|languages)\s*[:\-][^\n]*")
        in_role = sum(1 for r in roles if any(p.search(" " + LIST_LINE.sub("", r["block"]).lower() + " ") for p in pats))
        if in_role and "mentioned" in levels and len(levels) == 1:
            levels.add("project")
        best = max(levels, key=LEVELS.index)
        strong = [e for e in ev if LEVELS.index(e["level"]) >= 2]
        conf = "high" if len(strong) >= 2 or (strong and re.search(r"\d", " ".join(e["text"] for e in strong))) else "medium" if strong or best == "project" else "low"
        ev.sort(key=lambda e: -LEVELS.index(e["level"]))
        out[s] = {"level": best, "levels": sorted(levels, key=LEVELS.index), "evidence": ev[:3], "confidence": conf}
    return out


def relevant_years(roles, req_skills, lib):
    pats = [sk._pattern(a.lower()) for s in req_skills for a in sk.aliases(s, lib) if len(a) > 2 or a.isupper()]
    rel = [r for r in roles if any(p.search(" " + r["block"].lower() + " ") for p in pats)]
    m = merge_months(rel)
    return round(sum(e - s + 1 for s, e in m) / 12, 1) if m else 0.0


def _loc_match(req_loc, cand_loc, work_mode, resume):
    if (work_mode or "") == "remote":
        return 1.0, "Remote role: location not limiting."
    if not cand_loc:
        return 0.0, "Candidate location not known."
    rl = {x.strip().lower() for x in re.split(r",|/|\bor\b", (req_loc or "").replace("Bangalore", "Bengaluru").replace("Gurgaon", "Gurugram")) if x.strip()}
    cl = cand_loc.lower().replace("bangalore", "bengaluru").replace("gurgaon", "gurugram")
    if not rl or any(r in cl for r in rl):
        return 1.0, f"Location {cand_loc} matches."
    from .intake import CITIES
    india = {c.lower() for c in CITIES[:CITIES.index("London")]} | {"india", "bengaluru", "gurugram"}
    if "india" in rl and any(c in cl for c in india):
        return 1.0, f"{cand_loc} is in India; requirement is India-wide."
    if re.search(r"(?i)open to relocat|willing to relocat|ready to relocat", resume or ""):
        return 0.6, f"In {cand_loc}; resume says open to relocate."
    return 0.2, f"In {cand_loc}; requirement is {req_loc}."


def evaluate(req, cand, lib, today=None):
    """Score one candidate against one requirement. Returns the full assessment."""
    w = dict(DEFAULT_WEIGHTS)
    w.update(req.get("weights") or {})
    text = SENSITIVE.sub("", cand.get("resume_text") or "")
    exp = experience(text, today)
    mand = req.get("mandatory_skills") or []
    pref = req.get("preferred_skills") or []
    trans = req.get("transferable_skills") or []
    critical = req.get("critical_skills") or mand
    ev = skill_evidence(text, list(dict.fromkeys(mand + pref + trans)), lib, exp["roles"])
    br, notes = {}, {}

    # 1. mandatory skills
    if mand:
        credit = [LEVEL_CREDIT.get(ev[s]["level"], 0) for s in mand]
        br["mandatory"] = w["mandatory"] * sum(credit) / len(mand)
        notes["mandatory"] = "; ".join(f"{s}: {ev[s]['level'] or 'no evidence'}" for s in mand)
    else:
        br["mandatory"], notes["mandatory"] = 0, "No mandatory skills defined."
    # 2. relevant project experience
    rel = relevant_years(exp["roles"], mand or pref, lib)
    used = [s for s in mand if ev[s]["level"] and ev[s]["level"] != "mentioned"]
    need = req.get("exp_min") or 3
    share = len(used) / len(mand) if mand else 0
    if exp["roles"]:
        br["projects"] = w["projects"] * (0.6 * min(1, rel / need) + 0.4 * share)
        notes["projects"] = f"{rel:g} relevant years in roles that use the required stack; {len(used)}/{len(mand)} mandatory skills used in projects."
    else:  # no dated roles in the text (e.g. a profile summary): don't penalise missing dates, score on usage only
        br["projects"] = w["projects"] * share
        notes["projects"] = f"No dated roles in the source text; scored on usage only: {len(used)}/{len(mand)} mandatory skills shown in work context."
    # 3. hands-on
    core = mand + pref
    ho = [s for s in core if ev[s]["level"] and LEVELS.index(ev[s]["level"]) >= 2]
    br["hands_on"] = w["hands_on"] * (len(ho) / len(core) if core else 0)
    notes["hands_on"] = f"Hands-on evidence for {', '.join(ho) or 'none'}."
    # 4. architecture
    arch = [s for s in core if "architecture" in ev[s]["levels"]]
    arch_any = bool(re.search(CUES["architecture"], text.lower()))
    br["architecture"] = w["architecture"] * (1.0 if len(arch) >= 2 else 0.6 if arch else 0.3 if arch_any else 0)
    notes["architecture"] = f"Design/architecture evidence on: {', '.join(arch)}." if arch else ("General design wording, not tied to required skills." if arch_any else "No architecture evidence.")
    # 5. experience alignment
    yrs = exp["listed_years"] or (exp["total_years"] if exp["total_years"] is not None else cand.get("total_exp_years") or exp["stated_years"])
    mn, mx = req.get("exp_min"), req.get("exp_max")
    if yrs is None:
        br["experience"], notes["experience"] = 0, "Total experience could not be calculated."
    elif (mn is None or yrs >= mn) and (mx is None or yrs <= mx):
        br["experience"], notes["experience"] = w["experience"], f"{yrs:g} years, in range."
    elif (mn is not None and yrs >= mn - 1) and (mx is None or yrs <= mx + 2):
        br["experience"], notes["experience"] = w["experience"] * 0.6, f"{yrs:g} years, just outside range."
    else:
        br["experience"], notes["experience"] = w["experience"] * 0.2, f"{yrs:g} years, outside range."
    # 6. domain
    dom = (req.get("domain") or "").strip().lower()
    if not dom or dom == "none":
        br["domain"], notes["domain"] = w["domain"], "No domain requirement."
    else:
        hit = [d.strip() for d in dom.split(",") if d.strip() and re.search(r"(?i)\b" + re.escape(d.strip()), text)]
        br["domain"] = w["domain"] if hit else 0
        notes["domain"] = f"Domain evidence: {', '.join(hit)}." if hit else f"No {dom} evidence in resume."
    # 7. availability (claimed notice counts for less than verified)
    np_days = cand.get("notice_period_days")
    cap = req.get("notice_max_days")
    verified = bool(cand.get("availability_verified"))
    if np_days is None:
        br["availability"], notes["availability"] = 0, "Notice period unknown; ask on screening call."
    elif cap is None or np_days <= cap:
        br["availability"] = w["availability"] * (1.0 if verified else 0.6)
        notes["availability"] = f"{np_days} days notice ({'verified' if verified else 'claimed, not verified'})."
    else:
        br["availability"], notes["availability"] = w["availability"] * 0.2, f"{np_days} days notice exceeds the {cap}-day limit."
    # 8. location
    lf, ln = _loc_match(req.get("location"), cand.get("location"), req.get("work_mode"), text)
    br["location"], notes["location"] = w["location"] * lf, ln

    total = round(sum(br.values()), 1)
    missing = [s for s in mand if not ev[s]["level"]]
    weak = [s for s in mand if ev[s]["level"] == "mentioned"]
    crit_gaps = [s for s in critical if s in mand and (not ev[s]["level"] or ev[s]["level"] == "mentioned")]
    level_gaps = []
    for s, need in ((req.get("intake") or {}).get("required_levels") or {}).items():
        have = ev.get(s, {}).get("levels") or []
        if s in mand and need not in have and not any(LEVELS.index(h) > LEVELS.index(need) and need != "production" for h in have):
            level_gaps.append(s)
            if s not in crit_gaps and s in critical:
                crit_gaps.append(s)
    cls = "High-potential shortlist" if total >= 85 else "Potential shortlist" if total >= 70 else "Secondary pipeline" if total >= 55 else "Not recommended"
    if crit_gaps and total >= 55:
        rec = f"Hold: critical skill gap ({', '.join(crit_gaps)}). Verify before shortlisting."
    elif total >= 70:
        rec = "Shortlist"
    elif total >= 55:
        rec = "Keep in secondary pipeline"
    elif not exp["roles"]:
        rec = "Hold: thin source (no dated roles). Verify on a call before deciding."
    else:
        rec = "Reject"
    flags = []
    if crit_gaps:
        flags.append({"type": "critical_gap", "text": f"Missing or keyword-only evidence for critical skill(s): {', '.join(crit_gaps)}."})
    if "GCC Sales" in mand and re.search(r"(?i)\bgcc", text):
        gulf = re.search(r"(?i)\b(gulf|saudi|uae|dubai|qatar|kuwait|oman|bahrain|riyadh|abu dhabi|nordic)\b", text)
        capability = re.search(r"(?i)global capability|captive|\bgic\b|offshore cent|gcc setup|gcc advisory|gcc accounts|gcc business|india gcc|gccs\b", text)
        if gulf and not capability:
            flags.append({"type": "gcc_ambiguous", "text": "\"GCC\" here may mean the Gulf region (Gulf/Middle East words nearby), not Global Capability Centers. Confirm on the call."})
    for s in level_gaps:
        need = req["intake"]["required_levels"][s].replace("_", "-")
        flags.append({"type": "level_gap", "text": f"{s}: recruiter requires {need} evidence; resume shows {ev[s]['level'] or 'none'}."})
    for g in exp["gaps"]:
        flags.append({"type": "employment_gap", "text": f"{g['months']}-month gap ({g['from']} to {g['to']}). Ask about it; not scored."})
    if exp["stated_years"] and exp["total_years"] and abs(exp["stated_years"] - exp["total_years"]) >= 1.5:
        flags.append({"type": "experience_mismatch", "text": f"Resume states {exp['stated_years']:g} years; dates add up to {exp['total_years']:g}."})
    if cand.get("notice_status") == "immediate" and not verified:
        flags.append({"type": "availability_unverified", "text": "Marked immediate but not verified. Not counted as an immediate joiner."})
    qs = screening_questions(req, ev, lib, missing, weak)
    return {"total": total, "classification": cls, "recommendation": rec,
            "breakdown": {k: {"score": round(v, 1), "max": w[k], "evidence": notes[k]} for k, v in br.items()},
            "skill_evidence": ev, "missing_skills": missing, "keyword_only": weak, "critical_gaps": crit_gaps,
            "flags": flags, "screening_questions": qs, "relevant_exp_years": rel,
            "total_exp_years": yrs, "roles_found": len(exp["roles"]), "weights": w,
            "ignored_fields": "Personal details (age, gender, marital status, religion, photo, nationality) are removed before scoring."}


def screening_questions(req, ev, lib, missing, weak):
    qs = []
    for s in (req.get("mandatory_skills") or []):
        e = ev.get(s, {})
        bank = lib["skills"].get(s, {}).get("screening", [])
        sales = lib["skills"].get(s, {}).get("family") == "sales"
        if s in missing:
            q = (f"Where have you done {s.lower()}? Give one example: client, deal size, your role, and the result." if sales
                 else f"Have you used {s} in any project? What did you build with it, and when?")
            qs.append({"skill": s, "why": "No evidence in resume", "q": q})
        elif s in weak:
            q = (f"Your profile mentions {s.lower()}. Walk me through one deal or account where you did it yourself: client, value, timeline, outcome." if sales
                 else f"Your resume lists {s}. Walk me through one project where you used it hands-on: your part, the scale, the outcome.")
            qs.append({"skill": s, "why": "Listed but not shown in a project", "q": q})
        elif bank:
            qs.append({"skill": s, "why": f"Verify {e.get('level')} depth", "q": bank[0]})
        if e.get("level") in ("architecture",) and len(bank) > 1:
            qs.append({"skill": s, "why": "Architecture claim", "q": bank[1]})
    if req.get("notice_max_days") is not None:
        qs.append({"skill": "availability", "why": "Confirm availability", "q": "What is your notice period, is it negotiable, and do you have a last working day yet?"})
    return qs[:10]


def find_duplicates(db, cand):
    """Exact matches on normalised LinkedIn / GitHub / email; possible matches on name + company."""
    exact, possible = [], []
    for col, val in (("linkedin_norm", norm_url(cand.get("linkedin_url"))), ("github_norm", norm_url(cand.get("github_url"))), ("email_norm", norm_email(cand.get("email")))):
        if val:
            r = db.one(f"SELECT id, full_name FROM candidates WHERE {col}=?", (val,))
            if r:
                exact.append({"id": r["id"], "name": r["full_name"], "on": col.replace("_norm", "")})
    n = norm_name(cand.get("full_name"))
    if n and not exact:
        for r in db.q("SELECT id, full_name, current_company FROM candidates"):
            if norm_name(r["full_name"]) == n and norm_name(r["current_company"]) == norm_name(cand.get("current_company")):
                possible.append({"id": r["id"], "name": r["full_name"], "on": "name + company"})
    return exact, possible


def cross_check(req, cand, result, sourced_claims=None):
    """MARK and JOE challenge each other where the evidence does not support a call."""
    ch = []
    claims = sourced_claims or {}
    if claims.get("immediate_joiner") and not cand.get("availability_verified"):
        ch.append({"by": "JOE", "to": "MARK", "text": "MARK tagged this profile as an immediate joiner, but there is no verified evidence. Treat as unknown until confirmed."})
    if claims.get("open_to_work") and not cand.get("open_to_work_evidence"):
        ch.append({"by": "JOE", "to": "MARK", "text": "Open to Work was claimed without a source. Add the evidence or drop the tag."})
    if result["total"] >= 70 and result["keyword_only"]:
        ch.append({"by": "MARK", "to": "JOE", "text": f"Score is {result['total']:g}, but {', '.join(result['keyword_only'])} is only listed as a keyword. Confirm on a call before submitting."})
    if result["total"] < 55 and result["relevant_exp_years"] >= (req.get("exp_min") or 0) and not result["critical_gaps"]:
        ch.append({"by": "MARK", "to": "JOE", "text": "Low score but relevant experience is in range with no critical gap; the resume may be thin. Worth a quick call before rejecting."})
    if result["critical_gaps"] and result["total"] >= 70:
        ch.append({"by": "JOE", "to": "RECRUITER", "text": f"High overall score but critical gap on {', '.join(result['critical_gaps'])}. Not shortlisted until verified."})
    return ch
