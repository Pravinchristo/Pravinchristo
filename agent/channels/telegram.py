"""Telegram channel: message the agent from your phone, and receive its notifications.

Uses the Bot API over plain HTTPS (long polling), so there is no extra dependency and no public URL needed.
"""

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request

from ..core import Agent

log = logging.getLogger("agent.telegram")
MAX_LEN = 4000

HELP = """Send me any task in plain words. Commands:
/status - is the agent up, and what is scheduled
/skills - skills I have learned
/new - start a fresh conversation (memory and skills are kept)"""


class Telegram:
    def __init__(self, token: str, chat_id: str | None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.agent: Agent | None = None

    def _call(self, method: str, params: dict, timeout: int = 70) -> dict:
        data = urllib.parse.urlencode(params).encode()
        with urllib.request.urlopen(f"{self.base}/{method}", data=data, timeout=timeout) as resp:
            return json.loads(resp.read())

    def send(self, text: str, chat_id: str | None = None) -> bool:
        chat_id = chat_id or self.chat_id
        if not chat_id:
            log.warning("No TELEGRAM_CHAT_ID set; dropping notification: %s", text[:200])
            return False
        try:
            for i in range(0, max(len(text), 1), MAX_LEN):
                self._call("sendMessage", {"chat_id": chat_id, "text": text[i:i + MAX_LEN] or "(empty)"})
            return True
        except (urllib.error.URLError, TimeoutError) as e:
            log.error("Telegram send failed: %s", e)
            return False

    def _handle(self, chat_id: str, text: str) -> None:
        agent = self.agent
        if text in ("/start", "/help"):
            self.send(HELP, chat_id)
        elif text == "/status":
            self.send(f"Up and running.\n\nScheduled jobs:\n{agent.toolbox.run('list_schedules', {})}", chat_id)
        elif text == "/skills":
            skills = agent.skill_index()
            self.send("\n".join(f"• {p.removeprefix('skills/')}: {d}" for p, d in skills) or "No skills yet.", chat_id)
        elif text == "/new":
            agent.threads.reset(f"telegram-{chat_id}")
            self.send("Started a fresh conversation. Memory and skills are kept.", chat_id)
        else:
            self._call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=10)
            reply = agent.run(f"telegram-{chat_id}", text, source="telegram")
            self.send(reply or "(no reply)", chat_id)

    def run_forever(self, stop: threading.Event) -> None:
        log.info("Telegram polling started")
        offset = 0
        while not stop.is_set():
            try:
                updates = self._call("getUpdates", {"timeout": 50, "offset": offset})
            except Exception as e:
                log.warning("Telegram poll failed (%s); retrying", e)
                stop.wait(5)
                continue
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                if chat_id != self.chat_id:
                    # Only the owner may command the agent.
                    log.warning("Ignoring message from unauthorised chat %s", chat_id)
                    if not self.chat_id:
                        self.send(f"Not authorised. To make this chat the owner, set TELEGRAM_CHAT_ID={chat_id} "
                                  "and restart the agent.", chat_id)
                    continue
                # Handle each message in its own thread so polling never stalls on a long task.
                threading.Thread(target=self._safe_handle, args=(chat_id, text), daemon=True).start()

    def _safe_handle(self, chat_id: str, text: str) -> None:
        try:
            self._handle(chat_id, text)
        except Exception as e:
            log.exception("Failed handling Telegram message")
            self.send(f"Something went wrong: {e.__class__.__name__}. I'm still running.", chat_id)
