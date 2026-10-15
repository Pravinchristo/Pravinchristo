"""Entry point.

    python -m agent run          # 24/7 daemon: Telegram + scheduler + inbox watcher + nightly learning
    python -m agent chat         # chat in the terminal (same memory and skills)
    python -m agent ask "..."    # one-off task, prints the reply
"""

import argparse
import logging
import signal
import sys
import threading
import time

from .config import Config
from .core import Agent
from .scheduler import Scheduler

log = logging.getLogger("agent")


def _supervise(stop: threading.Event, workers: dict, heartbeat) -> None:
    """Keep every worker thread alive: if one dies, start it again."""
    threads: dict[str, threading.Thread] = {}
    while not stop.is_set():
        for name, target in workers.items():
            t = threads.get(name)
            if t is None or not t.is_alive():
                if t is not None:
                    log.error("Worker %s stopped unexpectedly; restarting", name)
                t = threading.Thread(target=target, args=(stop,), name=name, daemon=True)
                t.start()
                threads[name] = t
        heartbeat.write_text(str(int(time.time())))
        stop.wait(15)


def cmd_run(config: Config) -> None:
    telegram = None
    if config.telegram_token:
        from .channels.telegram import Telegram
        telegram = Telegram(config.telegram_token, config.telegram_chat_id)
    agent = Agent(config, notifier=telegram.send if telegram else None)
    if telegram:
        telegram.agent = agent
    else:
        log.warning("TELEGRAM_BOT_TOKEN not set: running scheduler and inbox only (no phone chat or notifications).")

    workers = {"scheduler": Scheduler(agent).run_forever}
    if telegram:
        workers["telegram"] = telegram.run_forever

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("Agent running (model %s, timezone %s). Workspace: %s", config.model, config.timezone, config.workspace)
    if telegram:
        telegram.send("Agent is online.")
    _supervise(stop, workers, config.data_dir / "heartbeat")
    log.info("Shutting down")


def cmd_chat(config: Config) -> None:
    agent = Agent(config)
    print("Chatting with your agent. Type /new for a fresh conversation, /quit to exit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text in ("/quit", "/exit"):
            return
        if text == "/new":
            agent.threads.reset("terminal")
            print("(fresh conversation)\n")
            continue
        print(f"\nagent> {agent.run('terminal', text, source='terminal')}\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run 24/7")
    sub.add_parser("chat", help="chat in the terminal")
    ask = sub.add_parser("ask", help="run one task and print the reply")
    ask.add_argument("task")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = Config.from_env()

    if args.command == "run":
        cmd_run(config)
    elif args.command == "chat":
        cmd_chat(config)
    else:
        print(Agent(config).run(f"ask-{int(time.time())}", args.task, source="cli"))


if __name__ == "__main__":
    main()
