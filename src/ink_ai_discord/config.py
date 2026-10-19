from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    discord_bot_token: str
    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    web_session_secret: str
    database_path: Path
    web_origin: str

    @classmethod
    def from_environment(cls) -> Settings:
        database_path = Path(
            os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "bot.sqlite3"))
        ).expanduser()
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        return cls(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
            discord_client_id=os.getenv("DISCORD_CLIENT_ID", "").strip(),
            discord_client_secret=os.getenv("DISCORD_CLIENT_SECRET", "").strip(),
            discord_redirect_uri=os.getenv(
                "DISCORD_REDIRECT_URI",
                "http://127.0.0.1:8080/auth/discord/callback",
            ).strip(),
            web_session_secret=os.getenv("WEB_SESSION_SECRET", "").strip(),
            database_path=database_path,
            web_origin=os.getenv("WEB_ORIGIN", "http://127.0.0.1:5173").rstrip("/"),
        )
