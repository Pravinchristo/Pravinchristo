---
name: searxng-search
description: Private web search through a self-hosted SearXNG metasearch instance (aggregates Google, DuckDuckGo, Brave, Wikipedia and more). Use when the user asks to search the web, look something up, find people/companies/candidates online, or research a topic and no other web search tool is available or the user asks for SearXNG.
---

# SearXNG Search

A local SearXNG server runs on `http://127.0.0.1:8888`. If it is not running, the search script starts it (the first run clones and installs SearXNG, which takes about a minute).

## Search

```bash
.claude/skills/searxng-search/scripts/search.sh "your query" [max_results] [categories]
```

- `max_results` defaults to 10.
- `categories` defaults to `general`. Others: `news`, `images`, `videos`, `it`, `science`, `files`, `social media`.
- Search operators work as usual, e.g. `site:linkedin.com/in "Client Partner" "Quality Engineering" Bengaluru`.

For raw JSON (all fields, engine names, scores):

```bash
curl -s --noproxy '*' -G -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8888/search \
  --data-urlencode "q=your query" --data-urlencode format=json
```

## Start or restart manually

```bash
.claude/skills/searxng-search/scripts/start.sh
```

Install files, settings and the log live in `~/.cache/searxng/` (`searxng.log` for errors).

## Troubleshooting

- **"Unresponsive engines … HTTP connection error"**: the environment's network policy is blocking the search sites. Allow these domains in the cloud environment's Network access settings: `html.duckduckgo.com`, `search.brave.com`, `www.google.com`, `en.wikipedia.org`, `query.wikidata.org` (plus any other engine you enable). Do not try to route around the block.
- **No results but no unresponsive engines**: try a broader query or another category.
- Report results with their URLs. Never invent results when the search fails; say what failed instead.
