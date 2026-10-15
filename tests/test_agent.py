"""Offline tests: a scripted fake client stands in for the API, so no key or network is needed.

    python -m unittest discover tests
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from anthropic.types.beta import BetaMessage

from agent.config import Config
from agent.core import Agent
from agent.scheduler import Scheduler, _is_due


def _msg(content, stop_reason):
    return BetaMessage.model_validate({
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    })


def _text(t):
    return {"type": "text", "text": t}


def _tool(i, name, inp):
    return {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": inp}


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = self
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.script.pop(0)


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        ws = self.tmp / "workspace"
        (ws / "skills").mkdir(parents=True)
        (ws / "INSTRUCTIONS.md").write_text("Be brief.")
        self.config = Config(workspace=ws, data_dir=self.tmp / "data", timezone=ZoneInfo("UTC"))
        for sub in ("inbox", "outputs"):
            (ws / sub).mkdir()
        for sub in ("threads", "activity"):
            (self.config.data_dir / sub).mkdir(parents=True)
        self.sent = []

    def agent(self, script):
        client = FakeClient(script)
        return Agent(self.config, notifier=lambda m: self.sent.append(m) or True, client=client), client

    def test_tool_loop_learns_skill_and_memory(self):
        agent, client = self.agent([
            _msg([_text("Saving that."),
                  _tool(1, "save_skill", {"name": "JD Writing", "description": "Write JDs",
                                          "content": "Use bullet points.", "reason": "user asked for bullets"}),
                  _tool(2, "remember", {"fact": "Prefers bullet-point JDs."})], "tool_use"),
            _msg([_text("Done, I'll use bullets from now on.")], "end_turn"),
        ])
        reply = agent.run("t1", "Always write JDs as bullets", "terminal")
        self.assertEqual(reply, "Done, I'll use bullets from now on.")
        skill = (self.config.workspace / "skills" / "jd-writing.md").read_text()
        self.assertIn("description: Write JDs", skill)
        self.assertIn("created** `jd-writing`", (self.config.workspace / "skills" / "CHANGELOG.md").read_text())
        self.assertIn("Prefers bullet-point JDs.", (self.config.workspace / "memory.md").read_text())

        # Both tool results go back in one user message, after the assistant turn.
        second = client.requests[1]["messages"]
        self.assertEqual([m["role"] for m in second], ["user", "assistant", "user"])
        self.assertEqual(len(second[2]["content"]), 2)
        # First turn carries instructions; system prompt is static.
        self.assertIn("Be brief.", second[0]["content"][0]["text"])
        self.assertEqual(client.requests[0]["system"], client.requests[1]["system"])
        self.assertEqual(client.requests[0]["fallbacks"], "default")

        activity = agent.activity.read(agent.now().date().isoformat())
        self.assertEqual(activity[0]["tools"], ["save_skill", "remember"])

    def test_context_only_resent_when_it_changes(self):
        agent, client = self.agent([_msg([_text("a")], "end_turn"), _msg([_text("b")], "end_turn"),
                                    _msg([_text("c")], "end_turn")])
        agent.run("t", "one", "terminal")
        agent.run("t", "two", "terminal")
        last_user = client.requests[1]["messages"][-1]["content"]
        self.assertEqual(len(last_user), 1)  # no context block: nothing changed
        (self.config.workspace / "memory.md").write_text("- new fact")
        agent.run("t", "three", "terminal")
        last_user = client.requests[2]["messages"][-1]["content"]
        self.assertIn("new fact", last_user[0]["text"])
        # History is append-only across turns.
        self.assertEqual(client.requests[2]["messages"][:4], client.requests[1]["messages"] + [
            client.requests[2]["messages"][3]])

    def test_sandbox_and_protected_instructions(self):
        agent, _ = self.agent([
            _msg([_tool(1, "write_file", {"path": "INSTRUCTIONS.md", "content": "x"}),
                  _tool(2, "read_file", {"path": "../../etc/passwd"}),
                  _tool(3, "write_file", {"path": "outputs/r.md", "content": "report"})], "tool_use"),
            _msg([_text("ok")], "end_turn"),
        ])
        agent.run("t", "go", "terminal")
        self.assertEqual((self.config.workspace / "INSTRUCTIONS.md").read_text(), "Be brief.")
        self.assertEqual((self.config.workspace / "outputs" / "r.md").read_text(), "report")
        results = json.loads((self.config.data_dir / "threads" / "t.json").read_text())["messages"][2]["content"]
        self.assertEqual([r["is_error"] for r in results], [True, True, False])

    def test_api_error_rolls_back_turn(self):
        import anthropic
        import httpx2

        class Boom(FakeClient):
            def create(self, **kwargs):
                raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x"))

        agent = Agent(self.config, client=Boom([]))
        reply = agent.run("t", "hello", "terminal")
        self.assertIn("API error", reply)
        self.assertEqual(agent.threads.load("t")["messages"], [])

    def test_schedule_tool_and_due_logic(self):
        agent, _ = self.agent([
            _msg([_tool(1, "schedule_task", {"name": "QA market scan", "prompt": "Scan.",
                                             "every_minutes": 0, "daily_at": "09:00"}),
                  _tool(2, "schedule_task", {"name": "bad", "prompt": "x", "every_minutes": 5, "daily_at": ""})],
                 "tool_use"),
            _msg([_text("scheduled")], "end_turn"),
        ])
        agent.run("t", "every morning scan the QA market", "terminal")
        jobs = agent.schedules.all()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        created = datetime.fromisoformat(job["last_run"])
        next_morning = (created + timedelta(days=1)).replace(hour=9, minute=0, second=1)
        self.assertTrue(_is_due(job, next_morning))
        self.assertFalse(_is_due({**job, "last_run": next_morning.isoformat()}, next_morning + timedelta(hours=1)))
        self.assertTrue(_is_due({"every_minutes": 30, "last_run": None}, created))

    def test_inbox_file_is_processed(self):
        agent, client = self.agent([_msg([_text("screened")], "end_turn")])
        f = self.config.workspace / "inbox" / "resume.txt"
        f.write_text("Jane Doe, SDET, Pytest")
        import os, time
        old = time.time() - 60
        os.utime(f, (old, old))
        sched = Scheduler(agent)
        sched._scan_inbox()
        for t in __import__("threading").enumerate():
            if t.name.startswith("job-"):
                t.join(5)
        self.assertTrue((self.config.workspace / "inbox" / "processed" / "resume.txt").exists())
        self.assertIn("inbox/processed/resume.txt", client.requests[0]["messages"][0]["content"][-1]["text"])


if __name__ == "__main__":
    unittest.main()
