"""Persistent state: conversation threads, the activity log, and schedules."""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

_write_lock = threading.Lock()


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


class ThreadStore:
    """Each thread is the full, append-only message history sent to the API."""

    def __init__(self, data_dir: Path):
        self.dir = data_dir / "threads"

    def _path(self, thread_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in thread_id)
        return self.dir / f"{safe}.json"

    def load(self, thread_id: str) -> dict:
        path = self._path(thread_id)
        if path.exists():
            return json.loads(path.read_text())
        return {"messages": [], "context_hash": None}

    def save(self, thread_id: str, thread: dict) -> None:
        with _write_lock:
            _atomic_write(self._path(thread_id), json.dumps(thread, ensure_ascii=False))

    def reset(self, thread_id: str) -> None:
        self._path(thread_id).unlink(missing_ok=True)


class ActivityLog:
    """One JSONL file per day: every request you made and what the agent did.

    The nightly reflection reads this to learn your preferences and patterns.
    """

    def __init__(self, data_dir: Path):
        self.dir = data_dir / "activity"

    def record(self, when: datetime, **entry) -> None:
        entry = {"time": when.isoformat(timespec="seconds"), **entry}
        with _write_lock, open(self.dir / f"{when.date().isoformat()}.jsonl", "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read(self, date: str) -> list[dict]:
        path = self.dir / f"{date}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class ScheduleStore:
    """Recurring jobs, kept in workspace/schedule.json so you can edit them by hand too."""

    def __init__(self, workspace: Path):
        self.path = workspace / "schedule.json"

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def _save(self, jobs: list[dict]) -> None:
        _atomic_write(self.path, json.dumps(jobs, indent=2, ensure_ascii=False))

    def add(self, name: str, prompt: str, every_minutes: int | None, daily_at: str | None,
            created: datetime) -> dict:
        job = {
            "id": uuid.uuid4().hex[:8],
            "name": name,
            "prompt": prompt,
            "every_minutes": every_minutes,
            "daily_at": daily_at,
            # Daily jobs first fire at their next daily_at, not the moment they are created.
            "last_run": created.isoformat(timespec="seconds") if daily_at else None,
            "enabled": True,
        }
        with _write_lock:
            jobs = self.all()
            jobs.append(job)
            self._save(jobs)
        return job

    def remove(self, job_id: str) -> bool:
        with _write_lock:
            jobs = self.all()
            kept = [j for j in jobs if j["id"] != job_id]
            self._save(kept)
        return len(kept) != len(jobs)

    def mark_run(self, job_id: str, when: datetime) -> None:
        with _write_lock:
            jobs = self.all()
            for j in jobs:
                if j["id"] == job_id:
                    j["last_run"] = when.isoformat(timespec="seconds")
            self._save(jobs)
