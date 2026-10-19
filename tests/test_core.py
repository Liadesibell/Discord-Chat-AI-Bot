from pathlib import Path
import time

from fastapi.testclient import TestClient

from ink_ai_discord.config import Settings
from ink_ai_discord.discord_bot import message_has_trigger, split_response
from ink_ai_discord.main import create_app
from ink_ai_discord.storage import GuildSettings, SettingsStore
from ink_ai_discord.web_search import extract_web_search_query


def test_settings_store_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "bot.sqlite3")
    settings = GuildSettings(
        enabled=False,
        respond_to_mentions=False,
        triggers=("help", "ink ai"),
        model="coder",
        system_prompt="Answer carefully.",
    )

    store.save_guild_settings("123", settings)

    assert store.get_guild_settings("123") == settings


def test_mention_and_trigger_matching_respects_configuration() -> None:
    mention = GuildSettings()
    assert message_has_trigger("Hi <@123>", 123, mention)
    assert not message_has_trigger("hello there", 123, mention)
    assert message_has_trigger("Orlin, 10x10 kaç eder?", 123, mention)
    assert message_has_trigger("ORLIN yardım eder misin?", 123, mention)
    assert not message_has_trigger("korlin yardım eder misin?", 123, mention)

    trigger = GuildSettings(respond_to_mentions=False, triggers=("help",))
    assert message_has_trigger("Can you HELP?", 123, trigger)
    assert not message_has_trigger("Hi <@123>", 123, trigger)

    disabled = GuildSettings(enabled=False, triggers=("help",))
    assert not message_has_trigger("help please", 123, disabled)


def test_web_search_is_only_requested_explicitly_and_extracts_topic() -> None:
    assert (
        extract_web_search_query(
            "Orlin bana bir web taraması yap: Türkiye'de yenilenebilir enerji"
        )
        == "Türkiye'de yenilenebilir enerji"
    )
    assert extract_web_search_query("Orlin Türkiye'de yenilenebilir enerji") is None
    assert extract_web_search_query("Orlin bana web taraması yap") == ""


def test_response_chunks_stay_within_discord_limit() -> None:
    chunks = split_response(("hello " * 200), limit=100)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "".join(chunk.replace(" ", "") for chunk in chunks) == "hello" * 200


def test_dashboard_requires_login_for_server_data(tmp_path: Path) -> None:
    settings = Settings(
        discord_bot_token="",
        discord_client_id="",
        discord_client_secret="",
        discord_redirect_uri="http://127.0.0.1:8080/auth/discord/callback",
        web_session_secret="test-session-secret",
        database_path=tmp_path / "bot.sqlite3",
        web_origin="http://127.0.0.1:5173",
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/me").json() == {"authenticated": False}
        assert client.get("/api/guilds").status_code == 401
        assert client.get("/api/status").status_code == 401
        callback = client.get(
            "/auth/discord/callback",
            params={"code": "unused", "state": "invalid"},
        )
        assert callback.status_code == 400


def test_auth_session_keeps_visible_and_manageable_guilds_separate(
    tmp_path: Path,
) -> None:
    store = SettingsStore(tmp_path / "bot.sqlite3")
    store.create_auth_session(
        "opaque-session",
        "user-1",
        "Ink User",
        {"guild-1", "guild-2"},
        {"guild-1"},
        int(time.time()) + 60,
    )

    session = store.get_auth_session("opaque-session")

    assert session is not None
    assert session["guild_ids"] == {"guild-1", "guild-2"}
    assert session["manageable_guild_ids"] == {"guild-1"}
