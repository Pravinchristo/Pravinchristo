"""Merge newly sourced OTT Test Engineer profiles into the master list and score them.

Usage:
    python3 score_and_merge.py EXISTING.json NEW.json OUT.json [--run-date YYYY-MM-DD]

EXISTING.json is the dashboard's current candidates file (rows, as this script
writes them), or "-" for the first run. NEW.json is a JSON array of candidate
records (see README.md for fields). OUT.json is the new dashboard file. Profiles are de-duplicated by
their LinkedIn URL; a profile seen again keeps its first `sourced_on` and
pipeline `stage`, and gets a fresh `last_seen`.
"""
import json
import re
import sys
from datetime import date

EXP_MIN, EXP_MAX = 2, 6
OPEN_SIGNALS = ("Open to work", "Immediate joiner")


def norm_url(url):
    url = url.strip().lower().replace("https://www.", "https://").rstrip("/")
    return re.sub(r"^http://", "https://", url)


def score(c):
    """0-100 fit score: OTT domain, analytics tools, experience band, availability."""
    s = 30 if c.get("ott_domain", True) else 10
    s += min(len(c.get("analytics_tools", [])), 3) * 10
    exp = c.get("exp_years")
    if exp is None:
        s += 10
    elif EXP_MIN <= exp <= EXP_MAX:
        s += 20
    s += 20 if c.get("availability") in OPEN_SIGNALS else 0
    return s


def tier(s):
    return "Hot" if s >= 75 else "Warm" if s >= 55 else "Nurture"


def from_row(r):
    """Turn a dashboard row back into a candidate record, so the dashboard file is the master list."""
    split = lambda v: [] if v in ("", "None stated") else v.split("; ")
    return {
        "name": r["name"], "profile_url": r["profile_url"], "headline": r["headline"],
        "company": r["company"], "city": r["city"], "exp_years": r["exp_years"],
        "availability": r["availability"], "analytics_tools": split(r["analytics_tools"]),
        "platforms": split(r["platforms"]), "ott_domain": r.get("ott_domain", True),
        "stage": r["stage"], "sourced_on": r["sourced_on"], "last_seen": r["last_seen"], "notes": r["notes"],
    }


def to_row(c):
    exp = c.get("exp_years")
    return {
        "candidate_id": norm_url(c["profile_url"]).rsplit("/", 1)[-1],
        "name": c["name"],
        "profile_url": c["profile_url"],
        "headline": c.get("headline", ""),
        "company": c.get("company") or "Not stated",
        "city": c.get("city") or "Not stated",
        "exp_years": exp,
        "exp_band": "Not stated" if exp is None else "2-3 yrs" if exp < 3.5 else "3.5-5 yrs" if exp <= 5 else "5-6 yrs",
        "availability": c.get("availability") or "Not stated",
        "analytics_tools": "; ".join(c.get("analytics_tools", [])) or "None stated",
        "analytics_tool_count": len(c.get("analytics_tools", [])),
        "platforms": "; ".join(c.get("platforms", [])),
        "ott_domain": c.get("ott_domain", True),
        "fit_score": score(c),
        "fit_tier": tier(score(c)),
        "stage": c.get("stage", "Sourced"),
        "sourced_on": c.get("sourced_on"),
        "last_seen": c.get("last_seen"),
        "notes": c.get("notes", ""),
    }


def main():
    args = sys.argv[1:]
    run_date = date.today().isoformat()
    if "--run-date" in args:
        i = args.index("--run-date")
        run_date = args[i + 1]
        del args[i:i + 2]
    existing_path, new_path, out_path = args
    existing = [] if existing_path == "-" else [from_row(r) for r in json.load(open(existing_path))]
    new = json.load(open(new_path))

    by_url = {norm_url(c["profile_url"]): c for c in existing}
    added = 0
    for c in new:
        key = norm_url(c["profile_url"])
        if key in by_url:
            old = by_url[key]
            c["sourced_on"] = old.get("sourced_on", run_date)
            c["stage"] = old.get("stage", "Sourced")
        else:
            c["sourced_on"] = c.get("sourced_on") or run_date
            added += 1
        c["last_seen"] = run_date
        by_url[key] = c

    rows = sorted((to_row(c) for c in by_url.values()), key=lambda r: (-r["fit_score"], r["name"]))
    json.dump(rows, open(out_path, "w"), indent=1)
    hot = sum(r["fit_tier"] == "Hot" for r in rows)
    print(json.dumps({"total": len(rows), "new": added, "hot": hot}))


if __name__ == "__main__":
    main()
