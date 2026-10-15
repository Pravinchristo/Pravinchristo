"""Runtime configuration, read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the agent runs without extra dependencies."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    model: str = "claude-opus-5-5"
    effort: str = "high"
    max_tokens: int = 16000
    max_steps: int = 40
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    workspace: Path = ROOT / "workspace"
    data_dir: Path = ROOT / "data"
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    reflect_at: str = "21:00"
    inbox_poll_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv(ROOT / ".env")
        cfg = cls(
            model=os.getenv("AGENT_MODEL", "claude-opus-5-5"),
            effort=os.getenv("AGENT_EFFORT", "high"),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "16000")),
            max_steps=int(os.getenv("AGENT_MAX_STEPS", "40")),
            timezone=ZoneInfo(os.getenv("AGENT_TIMEZONE", "UTC")),
            workspace=Path(os.getenv("AGENT_WORKSPACE", ROOT / "workspace")).resolve(),
            data_dir=Path(os.getenv("AGENT_DATA_DIR", ROOT / "data")).resolve(),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            reflect_at=os.getenv("AGENT_REFLECT_AT", "21:00"),
            inbox_poll_seconds=int(os.getenv("AGENT_INBOX_POLL_SECONDS", "60")),
        )
        for sub in ("skills", "inbox", "outputs"):
            (cfg.workspace / sub).mkdir(parents=True, exist_ok=True)
        for sub in ("threads", "activity"):
            (cfg.data_dir / sub).mkdir(parents=True, exist_ok=True)
        return cfg
