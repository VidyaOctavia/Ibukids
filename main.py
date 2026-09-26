from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import suppress
from typing import Optional

import discord
from aiohttp import web
from discord import app_commands


LOGGER = logging.getLogger("discord_voice_bot")
RECONNECT_INTERVAL_SECONDS = 20


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def parse_id(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a numeric Discord ID.") from error

    if parsed <= 0:
        raise RuntimeError(f"{name} must be a positive Discord ID.")

    return parsed


class VoiceStayBot(discord.Client):
    def __init__(self, voice_channel_id: int) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.voice_channel_id = voice_channel_id
        self.voice_supervisor: Optional[asyncio.Task[None]] = None
        self.health_runner: Optional[web.AppRunner] = None
        self.last_voice_error: Optional[str] = None
        self.last_voice_connection: Optional[str] = None
        self._command_sync_complete = False

    async def setup_hook(self) -> None:
        self.voice_supervisor = asyncio.create_task(
            self._maintain_voice_connection(),
            name="voice-connection-supervisor",
        )

        await self._start_health_server()

    async def on_ready(self) -> None:
        if not self._command_sync_complete:
            await self.tree.sync()
            self._command_sync_complete = True
            LOGGER.info("Application commands synced.")

        LOGGER.info(
            "Logged in as %s (%s).",
            self.user,
            self.user.id if self.user else "unknown",
        )

    async def close(self) -> None:
        if self.voice_supervisor:
            self.voice_supervisor.cancel()

            with suppress(asyncio.CancelledError):
                await self.voice_supervisor

        if self.health_runner:
            await self.health_runner.cleanup()

        await super().close()

    async def _maintain_voice_connection(self) -> None:
        await self.wait_until_ready()

        while not self.is_closed():
            try:
                channel = await self._resolve_voice_channel()

                if channel is None:
                    await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)
                    continue

                voice_client = channel.guild.voice_client

                if voice_client and voice_client.is_connected():
                    self.last_voice_connection = channel.name
                    self.last_voice_error = None
                else:
                    if voice_client:
                        await voice_client.disconnect(force=True)

                    LOGGER.info(
                        "Connecting to voice channel %s in %s.",
                        channel.name,
                        channel.guild.name,
                    )

                    await channel.connect(
                        reconnect=True,
                        self_deaf=True,
                        self_mute=True,
                    )

                    self.last_voice_connection = channel.name
                    self.last_voice_error = None

                    LOGGER.info(
                        "Connected to voice channel %s.",
                        channel.name,
                    )

            except asyncio.CancelledError:
                raise

            except (discord.Forbidden, discord.NotFound) as error:
                self.last_voice_error = str(error)

                LOGGER.error(
                    "Cannot access the configured voice channel: %s",
                    error,
                )

            except (discord.ClientException, asyncio.TimeoutError) as error:
                self.last_voice_error = str(error)

                LOGGER.warning(
                    "Voice connection dropped; retrying: %s",
                    error,
                )

            except Exception:
                self.last_voice_error = (
                    "Unexpected voice connection error; see logs."
                )

                LOGGER.exception(
                    "Unexpected error in voice connection supervisor."
                )

            await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)

    async def _resolve_voice_channel(
        self,
    ) -> Optional[discord.VoiceChannel]:
        for guild in self.guilds:
            channel = guild.get_channel(self.voice_channel_id)

            if isinstance(channel, discord.VoiceChannel):
                return channel

        LOGGER.warning(
            "Voice channel %s is not visible yet. "
            "Check the bot is in the server and has channel access.",
            self.voice_channel_id,
        )

        return None

    async def _start_health_server(self) -> None:
        app = web.Application()

        app.router.add_get("/health", self._health)
        app.router.add_get("/", self._health)

        self.health_runner = web.AppRunner(app)
        await self.health_runner.setup()

        port = int(os.getenv("PORT", "8008"))

        site = web.TCPSite(
            self.health_runner,
            host="0.0.0.0",
            port=port,
        )

        await site.start()

        LOGGER.info(
            "Health endpoint listening on port %s.",
            port,
        )

    async def _health(self, _request: web.Request) -> web.Response:
        voice_connected = any(
            voice_client.is_connected()
            for voice_client in self.voice_clients
        )

        return web.json_response(
            {
                "status": "ok" if self.is_ready() else "starting",
                "discord_ready": self.is_ready(),
                "voice_connected": voice_connected,
                "voice_channel": self.last_voice_connection,
                "last_voice_error": self.last_voice_error,
            }
        )


bot: Optional[VoiceStayBot] = None


@app_commands.command(
    name="voice-status",
    description="Show the bot's voice connection status.",
)
async def slash_voice_status(
    interaction: discord.Interaction,
) -> None:
    current_bot = interaction.client

    if not isinstance(current_bot, VoiceStayBot):
        await interaction.response.send_message(
            "Bot status is unavailable.",
            ephemeral=True,
        )
        return

    connected = next(
        (
            client
            for client in current_bot.voice_clients
            if client.is_connected()
        ),
        None,
    )

    if connected and connected.channel:
        message = (
            f"Connected to **{connected.channel.name}**."
        )
    else:
        message = (
            "Not connected yet. "
            "Automatic retries are enabled."
        )

    await interaction.response.send_message(
        message,
        ephemeral=True,
    )


async def run() -> None:
    global bot

    token = required_env("DISCORD_TOKEN")

    voice_channel_id = parse_id(
        "DISCORD_VOICE_CHANNEL_ID",
        required_env("DISCORD_VOICE_CHANNEL_ID"),
    )

    bot = VoiceStayBot(voice_channel_id)
    bot.tree.add_command(slash_voice_status)

    loop = asyncio.get_running_loop()

    for signal_name in ("SIGTERM", "SIGINT"):
        with suppress(NotImplementedError):
            loop.add_signal_handler(
                getattr(signal, signal_name),
                lambda: (
                    asyncio.create_task(bot.close())
                    if bot
                    else None
                ),
            )

    try:
        await bot.start(
            token,
            reconnect=True,
        )
    finally:
        await bot.close()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested.")


if __name__ == "__main__":
    main()
