#!/bin/bash
# Usage: search.sh "query" [max_results] [categories]
# Prints title, URL and snippet for each result, plus any engines that failed.
set -u
Q="${1:?usage: search.sh \"query\" [max_results] [categories]}"
N="${2:-10}"
CAT="${3:-general}"
PORT="${SEARXNG_PORT:-8888}"
DIR="$(cd "$(dirname "$0")" && pwd)"

curl -s -o /dev/null --noproxy '*' -m 2 "http://127.0.0.1:$PORT/healthz" || "$DIR/start.sh" >&2

curl -s --noproxy '*' -G -H 'X-Real-IP: 127.0.0.1' "http://127.0.0.1:$PORT/search" \
  --data-urlencode "q=$Q" --data-urlencode "format=json" --data-urlencode "categories=$CAT" |
python3 -c '
import sys, json
n = int(sys.argv[1])
d = json.load(sys.stdin)
res = d.get("results", [])[:n]
for i, r in enumerate(res, 1):
    title, url = r.get("title", ""), r.get("url", "")
    snippet = (r.get("content") or "").strip()[:300]
    print(f"{i}. {title}\n   {url}\n   {snippet}\n")
if not res:
    print("No results.")
bad = d.get("unresponsive_engines") or []
if bad:
    print("Unresponsive engines:", ", ".join(f"{e} ({why})" for e, why in bad))
' "$N"
