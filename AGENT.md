# 24/7 Personal AI Agent

An always-on agent powered by Claude. It follows **your instructions**, works on tasks you send from your
phone, runs scheduled jobs on its own, and **learns from what you do with it** by writing and improving its own skills.

## What it does

| | |
|---|---|
| **Follows your instructions** | `workspace/INSTRUCTIONS.md` is yours. The agent reads it before every task and is never allowed to edit it. |
| **Takes tasks any time** | Message it on Telegram (or `python -m agent chat` in a terminal). It can search and read the web. |
| **Works on its own** | Ask for anything recurring ("every weekday at 9, find new QA Automation openings in Chennai") and it creates a scheduled job and sends you the results. |
| **Watches an inbox** | Drop a resume, JD or notes into `workspace/inbox/` and it processes the file according to your instructions. |
| **Learns and updates its skills** | When you correct it or state a preference, it updates the matching skill on the spot. Every night (`AGENT_REFLECT_AT`, default 21:00) it reviews the day's activity log, improves its skills and memory, and sends you a digest of what it learned. |
| **Stays up** | A supervisor restarts any part that crashes. Docker or systemd restarts the whole process after a crash or reboot. |

## Where things live

```
workspace/
  INSTRUCTIONS.md     ← you write this; the agent obeys it
  memory.md           ← facts the agent has learned about you (you can edit them)
  skills/*.md         ← playbooks the agent follows and keeps improving
  skills/CHANGELOG.md ← every skill change, with the reason for it
  schedule.json       ← recurring jobs
  inbox/              ← drop files here for the agent to process
  outputs/            ← reports, candidate lists, drafts
data/                 ← conversation history + daily activity log (git-ignored)
```

## Setup

1. **API key.** Create a key at https://platform.claude.com/settings/keys.
2. **Telegram (recommended).** In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
3. `cp .env.example .env` and fill in `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN` and `AGENT_TIMEZONE`.
4. Start it (choose one of the options below), then message your bot. The first time, it replies with your
   chat id. Put that in `TELEGRAM_CHAT_ID` and restart. From then on it answers only you.

### Option A: Docker (simplest for 24/7)
```bash
docker compose up -d --build
docker compose logs -f
```

### Option B: Linux server with systemd
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo cp deploy/agent.service /etc/systemd/system/   # edit User/WorkingDirectory first
sudo systemctl daemon-reload && sudo systemctl enable --now agent
```

### Try it locally first
```bash
pip install -r requirements.txt
python -m agent chat                       # chat in the terminal
python -m agent ask "Boolean string for a Senior SDET, Python + Playwright, Bangalore"
```

A laptop only works while it's awake. For true 24/7, run the agent on a small always-on machine: any cloud VM
(AWS Lightsail, DigitalOcean, Hetzner, Oracle free tier) or a Raspberry Pi.

## Telegram commands
- `/status`: shows that the agent is up, plus its scheduled jobs
- `/skills`: lists what it has learned
- `/new`: starts a fresh conversation (memory and skills are kept)

## Safety boundaries
- File access is limited to `workspace/`. The agent can't run shell commands.
- It cannot email, post, or contact anyone but you. It writes drafts to `outputs/` for you to send.
- Telegram messages from any chat other than `TELEGRAM_CHAT_ID` are ignored.
- Web pages and inbox files are treated as information, not as instructions.

## Cost
Each request is billed by Anthropic per token. The model is Claude Opus 5.5 at `high` effort. To spend less,
set `AGENT_EFFORT=medium` (or `low`) in `.env`, or use fewer and less frequent scheduled jobs. You can see
spend in the Claude Console.

## Tests
```bash
python -m unittest discover tests     # offline; uses a fake API client
```
