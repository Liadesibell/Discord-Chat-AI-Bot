from __future__ import annotations

import asyncio
import hmac
import logging
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import discord
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from ink_ai_discord.config import Settings
from ink_ai_discord.discord_bot import InkDiscordBot
from ink_ai_discord.local_ai import LEGACY_MODEL_IDS, LocalAIClient
from ink_ai_discord.storage import GuildSettings, SettingsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)
DISCORD_API = "https://discord.com/api/v10"
DISCORD_ADMINISTRATOR = 0x8
DISCORD_MANAGE_GUILD = 0x20
AUTH_SESSION_SECONDS = 60 * 60 * 24 * 7


class GuildSettingsRequest(BaseModel):
    enabled: bool = True
    respond_to_mentions: bool = True
    triggers: list[str] = Field(default_factory=list, max_length=20)
    model: str = Field(
        default="auto",
        pattern="^(auto|deepseek|qwen35b|gpt_oss|gemma4)$",
    )
    system_prompt: str = Field(min_length=1, max_length=3_000)

    def to_settings(self) -> GuildSettings:
        cleaned_triggers = tuple(
            dict.fromkeys(trigger.strip() for trigger in self.triggers if trigger.strip())
        )
        if any(len(trigger) > 64 for trigger in cleaned_triggers):
            raise ValueError("Tetikleyiciler en fazla 64 karakter olabilir.")
        return GuildSettings(
            enabled=self.enabled,
            respond_to_mentions=self.respond_to_mentions,
            triggers=cleaned_triggers,
            model=self.model,
            system_prompt=self.system_prompt.strip(),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    store = SettingsStore(app_settings.database_path)
    ai_client = LocalAIClient()
    bot = InkDiscordBot(store, ai_client)
    bot_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        nonlocal bot_task
        application.state.store = store
        application.state.ai_client = ai_client
        application.state.bot = bot
        if app_settings.discord_bot_token:
            bot_task = asyncio.create_task(
                bot.start(app_settings.discord_bot_token),
                name="discord-bot",
            )

            def report_bot_failure(task: asyncio.Task[None]) -> None:
                if task.cancelled():
                    return
                error = task.exception()
                if error is not None:
                    LOGGER.error(
                        "Discord bot durdu.",
                        exc_info=(type(error), error, error.__traceback__),
                    )

            bot_task.add_done_callback(report_bot_failure)
        else:
            LOGGER.warning("DISCORD_BOT_TOKEN ayarlanmamış; Discord botu başlatılmadı.")
        yield
        if not bot.is_closed():
            await bot.close()
        if bot_task is not None:
            try:
                await asyncio.wait_for(bot_task, timeout=10)
            except (asyncio.TimeoutError, discord.LoginFailure, discord.HTTPException):
                if not bot_task.done():
                    bot_task.cancel()
        await asyncio.to_thread(ai_client.close)

    app = FastAPI(title="Orlin Discord Assistant", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.web_session_secret or secrets.token_urlsafe(48),
        session_cookie="ink_ai_discord_session",
        same_site="lax",
        https_only=False,
        max_age=AUTH_SESSION_SECONDS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def get_auth(request: Request) -> dict[str, object]:
        session_id = request.session.get("session_id")
        if not isinstance(session_id, str):
            raise HTTPException(status_code=401, detail="Discord ile giriş yapın.")
        session = store.get_auth_session(session_id)
        if session is None:
            request.session.clear()
            raise HTTPException(status_code=401, detail="Oturum süresi dolmuş.")
        return session

    def require_guild_access(request: Request, guild_id: str) -> dict[str, object]:
        if not guild_id.isdecimal():
            raise HTTPException(status_code=422, detail="Sunucu kimliği geçersiz.")
        auth = get_auth(request)
        manageable_guild_ids = auth["manageable_guild_ids"]
        if (
            not isinstance(manageable_guild_ids, set)
            or guild_id not in manageable_guild_ids
        ):
            raise HTTPException(status_code=403, detail="Bu sunucuyu yönetme izniniz yok.")
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            raise HTTPException(
                status_code=404,
                detail="Bot bu Discord sunucusunda bulunmuyor.",
            )
        return auth

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "discord_bot_ready": bot.is_ready(),
            "discord_guild_count": len(bot.guilds),
        }

    @app.get("/auth/discord/login")
    async def discord_login(request: Request):
        if not app_settings.discord_client_id or not app_settings.discord_client_secret:
            raise HTTPException(
                status_code=503,
                detail="DISCORD_CLIENT_ID ve DISCORD_CLIENT_SECRET ayarlanmalı.",
            )
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state
        query = urlencode(
            {
                "client_id": app_settings.discord_client_id,
                "redirect_uri": app_settings.discord_redirect_uri,
                "response_type": "code",
                "scope": "identify guilds",
                "state": state,
            }
        )
        return RedirectResponse(
            f"https://discord.com/oauth2/authorize?{query}",
            status_code=302,
        )

    @app.get("/auth/discord/callback")
    async def discord_callback(request: Request, code: str, state: str):
        expected_state = request.session.pop("oauth_state", None)
        if (
            not isinstance(expected_state, str)
            or not hmac.compare_digest(expected_state, state)
        ):
            raise HTTPException(status_code=400, detail="Discord OAuth state doğrulanamadı.")
        try:
            async with httpx.AsyncClient(timeout=15) as oauth_client:
                token_response = await oauth_client.post(
                    f"{DISCORD_API}/oauth2/token",
                    data={
                        "client_id": app_settings.discord_client_id,
                        "client_secret": app_settings.discord_client_secret,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": app_settings.discord_redirect_uri,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if token_response.is_error:
                    LOGGER.warning(
                        "Discord OAuth token isteği HTTP %s döndürdü.",
                        token_response.status_code,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail="Discord ile giriş tamamlanamadı.",
                    )
                token_payload = token_response.json()
                if not isinstance(token_payload, dict):
                    raise HTTPException(
                        status_code=502,
                        detail="Discord token yanıtı geçersiz.",
                    )
                access_token = token_payload.get("access_token")
                if not isinstance(access_token, str):
                    raise HTTPException(
                        status_code=502,
                        detail="Discord erişim anahtarı alınamadı.",
                    )
                authorization = {"Authorization": f"Bearer {access_token}"}
                user_response = await oauth_client.get(
                    f"{DISCORD_API}/users/@me",
                    headers=authorization,
                )
                guilds_response = await oauth_client.get(
                    f"{DISCORD_API}/users/@me/guilds",
                    headers=authorization,
                )
                if user_response.is_error or guilds_response.is_error:
                    raise HTTPException(
                        status_code=502,
                        detail="Discord kullanıcı bilgileri alınamadı.",
                    )
                user = user_response.json()
                guilds = guilds_response.json()
        except httpx.HTTPError as error:
            LOGGER.warning("Discord OAuth isteği başarısız (%s).", type(error).__name__)
            raise HTTPException(
                status_code=502,
                detail="Discord OAuth servisine ulaşılamadı.",
            ) from error
        except ValueError as error:
            LOGGER.warning("Discord OAuth yanıtı geçersiz JSON döndürdü.")
            raise HTTPException(
                status_code=502,
                detail="Discord OAuth yanıtı geçersiz.",
            ) from error

        if not isinstance(user, dict) or not isinstance(guilds, list):
            raise HTTPException(status_code=502, detail="Discord yanıt biçimi geçersiz.")
        user_id = user.get("id")
        username = user.get("global_name") or user.get("username")
        if not isinstance(user_id, str) or not isinstance(username, str):
            raise HTTPException(status_code=502, detail="Discord kullanıcı bilgileri eksik.")

        user_guilds: set[str] = set()
        manageable_guilds: set[str] = set()
        for guild in guilds:
            if not isinstance(guild, dict):
                continue
            guild_id = guild.get("id")
            permissions = guild.get("permissions")
            if not isinstance(guild_id, str):
                continue
            user_guilds.add(guild_id)
            if isinstance(permissions, bool) or not isinstance(permissions, (str, int)):
                continue
            try:
                permission_bits = int(permissions)
            except ValueError:
                continue
            if permission_bits & (DISCORD_ADMINISTRATOR | DISCORD_MANAGE_GUILD):
                manageable_guilds.add(guild_id)

        session_id = secrets.token_urlsafe(32)
        store.create_auth_session(
            session_id,
            user_id,
            username,
            user_guilds,
            manageable_guilds,
            int(time.time()) + AUTH_SESSION_SECONDS,
        )
        request.session.clear()
        request.session["session_id"] = session_id
        return RedirectResponse(app_settings.web_origin, status_code=302)

    @app.post("/auth/logout")
    async def logout(request: Request) -> dict[str, bool]:
        session_id = request.session.get("session_id")
        if isinstance(session_id, str):
            store.delete_auth_session(session_id)
        request.session.clear()
        return {"ok": True}

    @app.get("/api/me")
    async def me(request: Request) -> dict[str, object]:
        try:
            auth = get_auth(request)
        except HTTPException as error:
            if error.status_code == 401:
                return {"authenticated": False}
            raise
        return {
            "authenticated": True,
            "username": auth["username"],
            "user_id": auth["user_id"],
        }

    @app.get("/api/status")
    async def status(request: Request) -> dict[str, object]:
        get_auth(request)
        health_status = await ai_client.health()
        return {
            "discord": {
                "ready": bot.is_ready(),
                "guild_count": len(bot.guilds),
                "latency_ms": round(bot.latency * 1000) if bot.is_ready() else None,
            },
            "local_ai": health_status,
        }

    @app.get("/api/guilds")
    async def list_guilds(request: Request) -> dict[str, list[dict[str, object]]]:
        auth = get_auth(request)
        visible_guilds = auth["guild_ids"]
        manageable = auth["manageable_guild_ids"]
        if not isinstance(visible_guilds, set) or not isinstance(manageable, set):
            raise HTTPException(status_code=500, detail="Oturum izinleri okunamadı.")
        guilds = [
            {
                "id": str(guild.id),
                "name": guild.name,
                "icon": guild.icon.url if guild.icon else None,
                "settings": store.get_guild_settings(str(guild.id)).enabled,
                "can_manage": str(guild.id) in manageable,
            }
            for guild in sorted(bot.guilds, key=lambda item: item.name.casefold())
            if str(guild.id) in visible_guilds
        ]
        return {"guilds": guilds}

    @app.get("/api/guilds/{guild_id}/settings")
    async def get_guild_settings(
        request: Request,
        guild_id: str,
    ) -> dict[str, object]:
        require_guild_access(request, guild_id)
        saved = store.get_guild_settings(guild_id)
        return {
            "enabled": saved.enabled,
            "respond_to_mentions": saved.respond_to_mentions,
            "triggers": list(saved.triggers),
            "model": LEGACY_MODEL_IDS.get(saved.model, saved.model),
            "system_prompt": saved.system_prompt,
        }

    @app.put("/api/guilds/{guild_id}/settings")
    async def save_guild_settings(
        request: Request,
        guild_id: str,
        body: GuildSettingsRequest,
    ) -> dict[str, object]:
        if not guild_id.isdecimal():
            raise HTTPException(status_code=422, detail="Sunucu kimliği geçersiz.")
        require_guild_access(request, guild_id)
        try:
            saved = body.to_settings()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not saved.system_prompt:
            raise HTTPException(status_code=422, detail="Sistem talimatı boş olamaz.")
        store.save_guild_settings(guild_id, saved)
        return {"ok": True}

    @app.get("/api/invite")
    async def invite() -> dict[str, str | None]:
        url = None
        if app_settings.discord_client_id:
            url = (
                "https://discord.com/oauth2/authorize?"
                + urlencode(
                    {
                        "client_id": app_settings.discord_client_id,
                        "permissions": "68608",
                        "scope": "bot",
                    }
                )
            )
        return {"url": url}

    return app


app = create_app()
