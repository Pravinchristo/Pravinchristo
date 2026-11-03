#!/usr/bin/env python3
"""Build the interactive recruitment dashboard (and a candidates CSV) from strategy.json.

Usage:
  python3 build_dashboard.py strategy.json [--out DIR] [--name dashboard.html]

What it does:
  * validates required sections and field types (prints every problem, exits 1 on errors)
  * dedupes candidates by normalised profile URL (keeps the higher score)
  * derives a missing tier from score + rubric.tiers; gates_passed=false -> "Out"
  * writes DIR/dashboard.html (single self-contained file) and DIR/candidates.csv
"""
import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "dashboard_template.html")

REQUIRED = {
    "meta": dict, "brief": dict, "skills": list, "market": dict, "companies": list,
    "pools": list, "searches": list, "rubric": dict, "candidates": list,
}
OPTIONAL_LISTS = ["titles", "channels", "outreach", "plan"]


def norm_url(u):
    u = re.sub(r"^https?://(www\.|[a-z]{2}\.)?", "", (u or "").strip().lower())
    return u.split("?")[0].rstrip("/")


def validate(d):
    errs, warns = [], []
    for k, t in REQUIRED.items():
        if k not in d:
            errs.append(f"missing section '{k}'")
        elif not isinstance(d[k], t):
            errs.append(f"'{k}' should be {t.__name__}")
    if errs:
        return errs, warns
    for k in OPTIONAL_LISTS:
        d.setdefault(k, [])
        if not isinstance(d[k], list):
            errs.append(f"'{k}' should be a list")
    if not d["meta"].get("role"):
        errs.append("meta.role is required")
    if not d["brief"].get("summary"):
        warns.append("brief.summary is empty")
    if not d["brief"].get("must"):
        warns.append("brief.must is empty")
    for i, s in enumerate(d["skills"]):
        if not isinstance(s, dict) or not s.get("name"):
            errs.append(f"skills[{i}] needs a name")
    for i, s in enumerate(d["searches"]):
        if not isinstance(s, dict) or not s.get("query"):
            errs.append(f"searches[{i}] needs a query")
            continue
        q = s["query"]
        if q.count("(") != q.count(")"):
            warns.append(f"searches[{i}] '{s.get('label', '')}': unbalanced brackets")
        if q.count('"') % 2:
            warns.append(f"searches[{i}] '{s.get('label', '')}': unpaired quotes")
    for i, c in enumerate(d["companies"]):
        if not isinstance(c, dict) or not c.get("name"):
            errs.append(f"companies[{i}] needs a name")
        elif c.get("tier") not in ("T1", "T2", "T3"):
            warns.append(f"companies[{i}] '{c['name']}': tier should be T1/T2/T3")
    diff = d["market"].get("difficulty")
    if diff is not None and not (isinstance(diff, (int, float)) and 1 <= diff <= 10):
        warns.append("market.difficulty should be a number 1–10")
    for i, c in enumerate(d["candidates"]):
        if not isinstance(c, dict) or not c.get("name"):
            errs.append(f"candidates[{i}] needs a name")
            continue
        if not re.match(r"^https?://", c.get("url") or ""):
            errs.append(f"candidates[{i}] '{c['name']}': url must be a real http(s) link you saw")
        sc = c.get("score")
        if sc is not None and not (isinstance(sc, (int, float)) and 0 <= sc <= 100):
            errs.append(f"candidates[{i}] '{c['name']}': score must be 0–100")
    return errs, warns


def finalise(d):
    tiers = (d.get("rubric") or {}).get("tiers") or {"A": 70, "B": 55, "C": 40}
    best = {}
    for c in d["candidates"]:
        key = norm_url(c["url"])
        if key not in best or (c.get("score") or 0) > (best[key].get("score") or 0):
            best[key] = c
    dropped = len(d["candidates"]) - len(best)
    out = []
    for c in best.values():
        if c.get("gates_passed") is False:
            c["tier"] = "Out"
        elif not c.get("tier") and isinstance(c.get("score"), (int, float)):
            s = c["score"]
            c["tier"] = "A" if s >= tiers["A"] else "B" if s >= tiers["B"] else "C" if s >= tiers["C"] else "Out"
        c.setdefault("verified", "unverified")
        out.append(c)
    out.sort(key=lambda c: -(c.get("score") or 0))
    d["candidates"] = out
    return dropped


def write_csv(d, path):
    cols = ["tier", "score", "name", "url", "headline", "company", "location", "years", "pool",
            "avail", "verified", "strengths", "gaps", "next", "source"]

    def cell(v):
        v = "; ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v))
        return "'" + v if v[:1] in ("=", "+", "-", "@") else v  # spreadsheet formula-injection guard

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for c in d["candidates"]:
            w.writerow([cell(c.get(k)) for k in cols])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy")
    ap.add_argument("--out", default=".")
    ap.add_argument("--name", default="dashboard.html")
    a = ap.parse_args()

    with open(a.strategy, encoding="utf-8") as f:
        d = json.load(f)
    errs, warns = validate(d)
    for w in warns:
        print("WARN ", w)
    if errs:
        for e in errs:
            print("ERROR", e)
        sys.exit(1)
    dropped = finalise(d)

    os.makedirs(a.out, exist_ok=True)
    payload = json.dumps(d, ensure_ascii=False)
    # Safe inside <script type="application/json">: neutralise tag/comment openers.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    if "__STRATEGY_JSON__" not in html:
        sys.exit("template placeholder missing")
    html = html.replace("__STRATEGY_JSON__", payload)
    role = d["meta"]["role"]
    safe_title = role.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = html.replace("<title>Talent Intelligence Desk</title>", f"<title>{safe_title} · Talent Desk</title>", 1)
    html_path = os.path.join(a.out, a.name)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    csv_path = os.path.join(a.out, "candidates.csv")
    write_csv(d, csv_path)

    tiers = {}
    for c in d["candidates"]:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    print(json.dumps({
        "dashboard": html_path, "csv": csv_path,
        "candidates": len(d["candidates"]), "duplicates_dropped": dropped, "tiers": tiers,
        "companies": len(d["companies"]), "pools": len(d["pools"]), "searches": len(d["searches"]),
        "warnings": len(warns),
    }, indent=1))


if __name__ == "__main__":
    main()
