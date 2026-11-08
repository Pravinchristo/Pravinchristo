"""Skill Intelligence Engine: matching, expansion, equivalents, dependencies, job families."""
import json
import os
import re

from .db import DATA_DIR, now

_LIB = None


def library(db=None):
    """Seed library merged with any skills the recruiter added (stored in skill_library)."""
    global _LIB
    if _LIB is None:
        _LIB = json.load(open(os.path.join(DATA_DIR, "skills.json")))
    lib = {"skills": dict(_LIB["skills"]), "families": _LIB["families"]}
    if db is not None:
        for r in db.q("SELECT name, payload FROM skill_library"):
            lib["skills"][r["name"]] = r["payload"]
    return lib


def add_skill(db, name, aliases=None, equivalents=None, related=None, family="general", actor="recruiter"):
    payload = {"aliases": aliases or [name], "expansions": [], "equivalents": equivalents or [],
               "related": related or [], "dependencies": [], "family": family,
               "market_availability": "unknown", "screening": []}
    db.conn.execute("INSERT OR REPLACE INTO skill_library (name, payload, source, updated_at) VALUES (?,?,?,?)",
                    (name, json.dumps(payload), actor, now()))
    db.conn.commit()
    return payload


def _pattern(alias):
    a = re.escape(alias.lower())
    # word-ish boundaries that tolerate symbols such as C#, CI/CD, Node.js
    # a trailing "s"/"es" is allowed so "frameworks" matches "framework" and "AI agents" matches "AI agent"
    return re.compile(r"(?<![a-z0-9])" + a + r"(?:e?s)?(?![a-z0-9])")


def canonical(name, lib):
    """Map a free-text skill to a library skill name, or return the cleaned text."""
    n = name.strip()
    low = n.lower()
    for s, d in lib["skills"].items():
        if low == s.lower() or low in (a.lower() for a in d["aliases"]):
            return s
    return n


def find_skills(text, lib):
    """Return library skills mentioned in text, in order of first mention."""
    low = " " + (text or "").lower() + " "
    hits = []
    for s, d in lib["skills"].items():
        best = None
        for a in d["aliases"]:  # the canonical name is matched only if listed as an alias ("Go" is not)
            if len(a) <= 2 and a.upper() != a:  # skip tiny ambiguous aliases like "ts"
                continue
            m = _pattern(a).search(low)
            if m and (best is None or m.start() < best):
                best = m.start()
        if best is not None:
            hits.append((best, s))
    return [s for _, s in sorted(hits)]


def aliases(skill, lib):
    d = lib["skills"].get(skill)
    if not d:
        return [skill]
    out = []
    # the canonical name is a label; search only with listed aliases (e.g. "New Logo Hunting" and "Go" are not search terms)
    for a in d["aliases"]:
        if a.lower() not in (o.lower() for o in out):
            out.append(a)
    return out


def detect_family(text, skills, lib):
    low = (text or "").lower()
    scores = {}
    for fam, d in lib["families"].items():
        sc = sum(2 for k in d["detect"] if k in low)
        sc += sum(1 for s in skills if lib["skills"].get(s, {}).get("family") == fam)
        scores[fam] = sc
    best = max(scores, key=scores.get) if scores else None
    return best if best and scores[best] > 0 else None


def intelligence(mandatory, preferred, family, lib):
    """Full skill map for a requirement. Related skills are never promoted to mandatory."""
    fam = lib["families"].get(family or "", {})
    out = {"family": family, "family_label": fam.get("label"), "mandatory": [], "preferred": [],
           "transferable": [], "related": [], "dependencies": [], "alternate_designations": fam.get("alternate_designations", []),
           "titles": fam.get("titles", []), "emerging": fam.get("emerging", [])}
    seen = set(mandatory) | set(preferred)
    for group, names in (("mandatory", mandatory), ("preferred", preferred)):
        for s in names:
            d = lib["skills"].get(s, {})
            out[group].append({"skill": s, "expansions": d.get("expansions", []), "aliases": aliases(s, lib),
                               "market_availability": d.get("market_availability", "unknown"),
                               "in_library": s in lib["skills"]})
            for e in d.get("equivalents", []):
                if e not in seen:
                    out["transferable"].append({"skill": e, "instead_of": s})
                    seen.add(e)
            for r in d.get("related", []):
                if r not in seen:
                    out["related"].append({"skill": r, "via": s})
                    seen.add(r)
            for dep in d.get("dependencies", []):
                out["dependencies"].append({"skill": s, "depends_on": dep})
    return out
