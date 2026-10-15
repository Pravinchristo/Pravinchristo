"""Background work: recurring jobs, the inbox watcher, and the nightly learning review."""

import logging
import shutil
import threading
import time
from datetime import datetime, timedelta

from .core import Agent

log = logging.getLogger("agent.scheduler")

REFLECTION_PROMPT = """Nightly review for {date}. Use read_activity for {date} to see everything the user \
asked you today and how you responded. Then:
1. Find corrections, stated preferences, repeated kinds of requests, and anything that went badly.
2. Update or create skills with save_skill so tomorrow's work reflects what you learned (read each skill first \
and merge). Record durable facts about the user with remember. Skip anything one-off.
3. If a recurring request would be better as a scheduled job, suggest it; don't create it unless the user's \
instructions say you may.
4. Send the user a short notify_user digest: what you did today, what you learned, and which skills changed. \
If there was no activity, do nothing and don't notify."""

INBOX_PROMPT = """A new file was dropped into the inbox: {path}. Read it and handle it as the user's \
instructions and your skills describe (for example: screen a resume against open roles, summarise a JD, \
extract action items). Save any deliverable under outputs/ and notify_user with a short summary."""


def _is_due(job: dict, now: datetime) -> bool:
    if not job.get("enabled", True):
        return False
    last = datetime.fromisoformat(job["last_run"]) if job.get("last_run") else None
    if job.get("every_minutes"):
        return last is None or now - last >= timedelta(minutes=job["every_minutes"])
    if job.get("daily_at"):
        hh, mm = map(int, job["daily_at"].split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return now >= target and (last is None or last < target)
    return False


class Scheduler:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.inbox = agent.config.workspace / "inbox"
        self.processed = self.inbox / "processed"
        self._last_inbox_scan = 0.0
        self._reflection_marker = agent.config.data_dir / "last_reflection"
        self._last_reflection_date = (self._reflection_marker.read_text().strip()
                                      if self._reflection_marker.exists() else None)
        self._busy: set[str] = set()
        self._busy_lock = threading.Lock()

    def _spawn(self, key: str, fn, *args) -> None:
        """Run a job in its own thread so a long job never blocks the others."""
        with self._busy_lock:
            if key in self._busy:
                return
            self._busy.add(key)

        def wrapper():
            try:
                fn(*args)
            except Exception:
                log.exception("Background job %s failed", key)
            finally:
                with self._busy_lock:
                    self._busy.discard(key)

        threading.Thread(target=wrapper, name=f"job-{key}", daemon=True).start()

    def tick(self) -> None:
        now = self.agent.now()
        for job in self.agent.schedules.all():
            if _is_due(job, now):
                self.agent.schedules.mark_run(job["id"], now)
                self._spawn(f"sched-{job['id']}", self._run_job, job, now)

        hh, mm = map(int, self.agent.config.reflect_at.split(":"))
        today = now.date().isoformat()
        if (now.hour, now.minute) >= (hh, mm) and self._last_reflection_date != today:
            self._last_reflection_date = today
            self._reflection_marker.write_text(today)
            self._spawn("reflection", self._reflect, now)

        if time.monotonic() - self._last_inbox_scan >= self.agent.config.inbox_poll_seconds:
            self._last_inbox_scan = time.monotonic()
            self._scan_inbox()

    def _run_job(self, job: dict, now: datetime) -> None:
        log.info("Running scheduled job %s (%s)", job["name"], job["id"])
        prompt = (f"Scheduled job '{job['name']}'. Run it now and notify_user with the results "
                  f"(skip the notification if there is nothing new).\n\n{job['prompt']}")
        # A fresh thread per run keeps each run self-contained; skills and memory carry the learning.
        self.agent.run(f"sched-{job['id']}-{now:%Y%m%d%H%M}", prompt, source="schedule")

    def _reflect(self, now: datetime) -> None:
        log.info("Running nightly reflection")
        date = now.date().isoformat()
        if not self.agent.activity.read(date):
            return
        self.agent.run(f"reflect-{date}", REFLECTION_PROMPT.format(date=date), source="reflection")

    def _scan_inbox(self) -> None:
        self.processed.mkdir(exist_ok=True)
        for path in sorted(self.inbox.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            # Skip files still being written.
            if time.time() - path.stat().st_mtime < 10:
                continue
            dest = self.processed / path.name
            shutil.move(str(path), dest)
            rel = dest.relative_to(self.agent.config.workspace).as_posix()
            self._spawn(f"inbox-{path.name}", self.agent.run,
                        f"inbox-{path.stem}", INBOX_PROMPT.format(path=rel), "inbox")

    def run_forever(self, stop: threading.Event) -> None:
        log.info("Scheduler started")
        while not stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("Scheduler tick failed")
            stop.wait(20)
