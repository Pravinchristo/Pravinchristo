"""Client-side tools the agent can call. File access is sandboxed to the workspace."""

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from .store import ActivityLog, ScheduleStore

PROTECTED_FILES = {"INSTRUCTIONS.md"}  # your instructions: the agent may read but never rewrite them
MAX_READ_CHARS = 200_000


def _tool(name: str, description: str, properties: dict) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOL_DEFINITIONS = [
    _tool(
        "list_files",
        "List files under a folder of the workspace (e.g. '', 'skills', 'inbox', 'outputs').",
        {"folder": {"type": "string", "description": "Folder relative to the workspace root; '' for the root."}},
    ),
    _tool(
        "read_file",
        "Read a text file from the workspace, e.g. a skill, memory.md, INSTRUCTIONS.md, or an inbox file.",
        {"path": {"type": "string", "description": "Path relative to the workspace root."}},
    ),
    _tool(
        "write_file",
        "Create or overwrite a text file in the workspace. Use outputs/ for deliverables (reports, drafts, "
        "candidate lists). INSTRUCTIONS.md is owned by the user and cannot be written.",
        {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
            "content": {"type": "string", "description": "Full file content."},
        },
    ),
    _tool(
        "save_skill",
        "Create or update a reusable skill: a playbook for a recurring kind of task. Call this when you learn "
        "a better way to do something the user asks for repeatedly, or when the user corrects how you did it. "
        "Read the existing skill first and merge, rather than discarding what is already there.",
        {
            "name": {"type": "string", "description": "Short kebab-case name, e.g. 'boolean-sourcing'."},
            "description": {"type": "string", "description": "One line: when to use this skill."},
            "content": {"type": "string", "description": "The full playbook in Markdown (steps, templates, preferences, pitfalls)."},
            "reason": {"type": "string", "description": "What prompted this change (shown to the user in the changelog)."},
        },
    ),
    _tool(
        "remember",
        "Save a durable fact about the user, their work, preferences, or contacts to long-term memory.",
        {"fact": {"type": "string", "description": "One self-contained fact."}},
    ),
    _tool(
        "schedule_task",
        "Create a recurring job that runs a prompt on its own. Use every_minutes for intervals (minimum 15) "
        "OR daily_at for a daily time in the user's timezone; set the unused one to 0 or ''.",
        {
            "name": {"type": "string"},
            "prompt": {"type": "string", "description": "Full standalone instruction to run each time."},
            "every_minutes": {"type": "integer", "description": "Interval in minutes, or 0."},
            "daily_at": {"type": "string", "description": "HH:MM 24-hour, or ''."},
        },
    ),
    _tool("list_schedules", "List recurring jobs.", {}),
    _tool("remove_schedule", "Delete a recurring job by id.", {"job_id": {"type": "string"}}),
    _tool(
        "read_activity",
        "Read the activity log for a day: every request the user made and how you responded.",
        {"date": {"type": "string", "description": "YYYY-MM-DD"}},
    ),
    _tool(
        "notify_user",
        "Send a message to the user's phone (Telegram). Use for scheduled or background work whose results "
        "the user should see; in a live chat your reply already reaches them.",
        {"message": {"type": "string"}},
    ),
]

SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 15},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 15},
]


class ToolError(Exception):
    pass


class Toolbox:
    def __init__(self, workspace: Path, activity: ActivityLog, schedules: ScheduleStore,
                 notifier: Callable[[str], bool], now: Callable[[], datetime]):
        self.workspace = workspace
        self.activity = activity
        self.schedules = schedules
        self.notifier = notifier
        self.now = now

    def _resolve(self, rel: str) -> Path:
        path = (self.workspace / rel.lstrip("/")).resolve()
        if path != self.workspace and self.workspace not in path.parents:
            raise ToolError(f"'{rel}' is outside the workspace.")
        return path

    def run(self, name: str, args: dict) -> str:
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            raise ToolError(f"Unknown tool '{name}'.")
        return handler(**args)

    def _t_list_files(self, folder: str) -> str:
        base = self._resolve(folder)
        if not base.is_dir():
            raise ToolError(f"'{folder}' is not a folder.")
        entries = sorted(p.relative_to(self.workspace).as_posix() + ("/" if p.is_dir() else "")
                         for p in base.iterdir() if not p.name.startswith("."))
        return "\n".join(entries) or "(empty)"

    def _t_read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError(f"'{path}' does not exist.")
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            raise ToolError(f"'{path}' is not a text file. Ask the user for a text/Markdown/CSV version.")
        if len(text) > MAX_READ_CHARS:
            return text[:MAX_READ_CHARS] + f"\n\n[... truncated: file is {len(text)} characters]"
        return text

    def _t_write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        if p.name in PROTECTED_FILES and p.parent == self.workspace:
            raise ToolError("INSTRUCTIONS.md belongs to the user. Suggest the change to them instead.")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Wrote {len(content)} characters to {path}."

    def _t_save_skill(self, name: str, description: str, content: str, reason: str) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
        if not slug:
            raise ToolError("Skill name is empty.")
        path = self.workspace / "skills" / f"{slug}.md"
        existed = path.exists()
        description = " ".join(description.split())
        path.write_text(f"---\nname: {slug}\ndescription: {description}\n---\n\n{content.strip()}\n")
        stamp = self.now().strftime("%Y-%m-%d %H:%M")
        with open(self.workspace / "skills" / "CHANGELOG.md", "a") as f:
            f.write(f"- {stamp} **{'updated' if existed else 'created'}** `{slug}`: {reason}\n")
        return f"Skill '{slug}' {'updated' if existed else 'created'}."

    def _t_remember(self, fact: str) -> str:
        with open(self.workspace / "memory.md", "a") as f:
            f.write(f"- ({self.now().date().isoformat()}) {' '.join(fact.split())}\n")
        return "Saved to memory."

    def _t_schedule_task(self, name: str, prompt: str, every_minutes: int, daily_at: str) -> str:
        if bool(every_minutes) == bool(daily_at):
            raise ToolError("Set exactly one of every_minutes or daily_at.")
        if every_minutes and every_minutes < 15:
            raise ToolError("every_minutes must be at least 15.")
        if daily_at and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", daily_at):
            raise ToolError("daily_at must be HH:MM (24-hour).")
        job = self.schedules.add(name, prompt, every_minutes or None, daily_at or None, self.now())
        return f"Scheduled '{name}' (id {job['id']})."

    def _t_list_schedules(self) -> str:
        jobs = self.schedules.all()
        if not jobs:
            return "No scheduled jobs."
        return "\n".join(
            f"{j['id']}: {j['name']} - "
            f"{'every ' + str(j['every_minutes']) + ' min' if j.get('every_minutes') else 'daily at ' + str(j.get('daily_at'))}"
            f"{'' if j.get('enabled', True) else ' (disabled)'}; last run {j.get('last_run') or 'never'}"
            for j in jobs
        )

    def _t_remove_schedule(self, job_id: str) -> str:
        return "Removed." if self.schedules.remove(job_id) else f"No job with id {job_id}."

    def _t_read_activity(self, date: str) -> str:
        entries = self.activity.read(date)
        if not entries:
            return f"No activity recorded on {date}."
        lines = []
        for e in entries:
            lines.append(f"[{e['time']} via {e.get('source')}] USER: {e.get('request', '')}")
            if e.get("tools"):
                lines.append(f"  tools used: {', '.join(e['tools'])}")
            lines.append(f"  AGENT: {e.get('reply', '')[:1500]}")
        return "\n".join(lines)

    def _t_notify_user(self, message: str) -> str:
        return "Sent." if self.notifier(message) else "No notification channel configured; message logged only."
