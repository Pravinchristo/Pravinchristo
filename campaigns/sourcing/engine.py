#!/usr/bin/env python3
"""Sourcing campaign engine: rotation, no-repeat ledger, reports and app-ready records.

  engine.py next                         -> companies for the next run
  engine.py seen <url>...                -> prints which URLs were already delivered or skipped
  engine.py record <run> <curated.json>  -> records a run (curated profiles + skipped URLs),
                                            writes reports/run-NNN.md and reports/run-NNN.app.json

curated.json: {"profiles": [{name,url,head,loc,company,years,tier,score,strengths[],gaps[],next}],
               "skipped": [url, ...]}
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = json.load(open(os.path.join(HERE, "targets.json")))
LEDGER = os.path.join(HERE, "ledger.json")
PER_RUN = 4


def norm(url):
    return re.sub(r"^https?://(www\.|[a-z]{2}\.)?", "", url).rstrip("/").lower()


def doc_id(url):
    h = 7
    for ch in norm(url):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    s = ""
    while True:
        h, r = divmod(h, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if h == 0:
            return "cf" + s


def load():
    if os.path.exists(LEDGER):
        return json.load(open(LEDGER))
    urls = json.load(open(os.path.join(HERE, "seed-urls.json")))
    return {"next_company": 0, "runs": 0, "seen": {norm(u): {"run": 0, "status": "pre-campaign"} for u in urls}}


def main():
    led = load()
    cmd = sys.argv[1]
    comps = TARGETS["companies"]
    if cmd == "next":
        i = led["next_company"] % len(comps)
        print(json.dumps({"run": led["runs"] + 1, "companies": [comps[(i + k) % len(comps)]["name"] for k in range(PER_RUN)]}))
    elif cmd == "seen":
        for u in sys.argv[2:]:
            print(("SEEN " if norm(u) in led["seen"] else "NEW  ") + u)
    elif cmd == "record":
        run, cur = int(sys.argv[2]), json.load(open(sys.argv[3]))
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fresh, repeats = [], 0
        for p in cur["profiles"]:
            if norm(p["url"]) in led["seen"]:
                repeats += 1
                continue
            led["seen"][norm(p["url"])] = {"run": run, "status": "delivered", "tier": p["tier"]}
            fresh.append(p)
        for u in cur.get("skipped", []):
            led["seen"].setdefault(norm(u), {"run": run, "status": "skipped"})
        fresh.sort(key=lambda p: -p["score"])
        companies = [comps[(led["next_company"] + k) % len(comps)]["name"] for k in range(PER_RUN)]
        led["runs"] = run
        led["next_company"] += PER_RUN
        json.dump(led, open(LEDGER, "w"), indent=1, sort_keys=True)
        app = [{
            "id": doc_id(p["url"]), "name": p["name"], "url": p["url"], "head": p["head"], "loc": p["loc"],
            "text": p.get("text", p["head"]), "source": f"Campaign run {run} · {p['company']}", "years": p.get("years"),
            "added": now, "screen": {"score": p["score"], "tier": p["tier"], "strengths": p["strengths"],
                                     "gaps": p["gaps"], "next": p["next"], "via": "campaign"}} for p in fresh]
        rdir = os.path.join(HERE, "reports")
        os.makedirs(rdir, exist_ok=True)
        json.dump(app, open(os.path.join(rdir, f"run-{run:03d}.app.json"), "w"), indent=1, ensure_ascii=False)
        rows = [f"# Run {run} · {now[:16].replace('T', ' ')} UTC", "", f"Companies hunted: {', '.join(companies)}",
                f"{len(fresh)} new profiles · {repeats} repeats dropped · {len(cur.get('skipped', []))} screened out", "",
                "| Tier | Score | Name | Current role | City | Years | Why | Watch-outs |", "|---|---|---|---|---|---|---|---|"]
        for p in fresh:
            rows.append(f"| {p['tier']} | {p['score']} | [{p['name']}]({p['url']}) | {p['head']} | {p['loc']} | {p.get('years') or '?'} | "
                        f"{'; '.join(p['strengths'])} | {'; '.join(p['gaps'])} |")
        open(os.path.join(rdir, f"run-{run:03d}.md"), "w").write("\n".join(rows) + "\n")
        print(json.dumps({"run": run, "new": len(fresh), "repeats": repeats, "ledger_size": len(led["seen"])}))


if __name__ == "__main__":
    main()
