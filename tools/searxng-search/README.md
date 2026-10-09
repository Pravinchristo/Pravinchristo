# SearXNG search skill (pending install)

These files are a ready-made Claude Code skill. They live here because installing them into `.claude/` changes Claude's own configuration, so that step needs your OK.

## Install

From the repository root:

```bash
mkdir -p .claude/skills
cp -r tools/searxng-search .claude/skills/searxng-search
rm .claude/skills/searxng-search/README.md
chmod +x .claude/skills/searxng-search/scripts/*.sh
```

## Optional: start SearXNG automatically in cloud sessions

Create `.claude/settings.json` with:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "[ \"$CLAUDE_CODE_REMOTE\" = \"true\" ] && (\"$CLAUDE_PROJECT_DIR\"/.claude/skills/searxng-search/scripts/start.sh > /dev/null 2>&1 &) ; exit 0"
          }
        ]
      }
    ]
  }
}
```

Without the hook, the search script still starts SearXNG on first use.

## Network access

The search engines must be reachable. In the cloud environment's Network access settings, allow:

- `html.duckduckgo.com`
- `search.brave.com`
- `www.google.com`
- `en.wikipedia.org`
- `query.wikidata.org`
