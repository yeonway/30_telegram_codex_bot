"""Discord Gateway adapter for the Codex relay core."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import logging
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from relay_errors import RelayError


LOG = logging.getLogger("telegram-codex-bot.discord")
DISCORD_TEXT_LIMIT = 1900
DISCORD_ATTACHMENT_HOSTS = {"cdn.discordapp.com", "media.discordapp.net"}
DISCORD_START_TIMEOUT_SECONDS = 30


class DiscordBridgeError(RelayError):
    pass


def _split_text(text: str, limit: int = DISCORD_TEXT_LIMIT) -> list[str]:
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


class DiscordBridge:
    def __init__(
        self,
        application: Any,
        token: str,
        allowed_user_id: int | None,
        allowed_channel_id: int | None,
    ) -> None:
        try:
            import discord
        except ImportError as exc:
            raise DiscordBridgeError(
                "discord.py is required when DISCORD_BOT_TOKEN is set"
            ) from exc

        self.application = application
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.allowed_channel_id = allowed_channel_id
        self._discord = discord
        intents = discord.Intents.default()
        # Discord exposes direct-message content without the privileged guild
        # Message Content Intent. Request it only when one server channel is enabled.
        intents.message_content = allowed_channel_id is not None
        self.client = discord.Client(intents=intents)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = threading.Event()
        self._controls_sent = False

        from discord_controls import DiscordControls

        self.controls = DiscordControls(self)

        @self.client.event
        async def on_ready() -> None:
            self._loop = asyncio.get_running_loop()
            self._started.set()
            LOG.info("Discord bridge connected")
            if self.allowed_user_id is not None and not self._controls_sent:
                try:
                    await self.controls.send_initial_panel()
                    self._controls_sent = True
                    LOG.info("Discord control panel sent")
                except Exception:
                    LOG.exception("Failed to send Discord control panel")

        @self.client.event
        async def on_message(message: Any) -> None:
            await self._handle_message(message)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="discord-gateway",
            daemon=True,
        )
        self._thread.start()

    def wait_until_ready(self, timeout: float = DISCORD_START_TIMEOUT_SECONDS) -> None:
        if self._started.wait(timeout):
            self.ensure_running()
            return
        thread = self._thread
        if thread is None or not thread.is_alive():
            raise DiscordBridgeError("Discord Gateway stopped before becoming ready")
        raise DiscordBridgeError(
            f"Discord Gateway did not become ready within {timeout:g} seconds"
        )

    def ensure_running(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            raise DiscordBridgeError("Discord Gateway worker is not running")

    def _run(self) -> None:
        try:
            self.client.run(self.token, log_handler=None)
        except Exception:
            LOG.exception("Discord Gateway stopped unexpectedly")

    async def _handle_message(self, message: Any) -> None:
        if message.author.bot:
            return
        is_dm = message.guild is None
        raw_content = (message.content or "").strip()
        if self.allowed_user_id is None:
            if not is_dm or not raw_content.lower().startswith(("!pair ", "/pair ")):
                return
        elif int(message.author.id) != self.allowed_user_id:
            LOG.warning("Rejected unauthorized Discord user")
            return
        channel_id = int(message.channel.id)
        # A configured server channel supplements the authorized user's DM;
        # it must not disable DM replies after the bot joins a server.
        if not is_dm and (
            self.allowed_channel_id is None or channel_id != self.allowed_channel_id
        ):
            return

        content = raw_content
        if content.lower() in {"!panel", "!menu", "/panel", "/menu"}:
            await self.controls.send_panel(message.channel)
            return
        if content.startswith("!"):
            content = "/" + content[1:]
        photos = []
        files = []
        for attachment in message.attachments:
            content_type = (attachment.content_type or "").lower()
            if content_type.startswith("image/"):
                photos.append(
                    {
                        "file_id": f"discord:{attachment.url}",
                        "file_size": attachment.size,
                    }
                )
            else:
                files.append(
                    {
                        "file_id": f"discord:{attachment.url}",
                        "file_size": attachment.size,
                        "file_name": attachment.filename,
                    }
                )
        update = {
            "message": {
                "_platform": "discord",
                "chat": {
                    "id": -channel_id,
                    "type": "private" if is_dm else "channel",
                },
                "from": {"id": -int(message.author.id)},
                "text": content if content and not (photos or files) else None,
                "caption": content if (photos or files) else None,
                "photo": photos,
                "attachment": files,
            }
        }
        await asyncio.to_thread(self.application.handle_update, update)

    def _submit(self, coroutine: Any) -> Any:
        loop = self._loop
        if (
            loop is None
            or loop.is_closed()
            or not loop.is_running()
            or not self._started.is_set()
        ):
            coroutine.close()
            raise DiscordBridgeError("Discord Gateway is not ready")
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except RuntimeError as exc:
            coroutine.close()
            raise DiscordBridgeError("Discord Gateway is not ready") from exc
        try:
            return future.result(timeout=30)
        except Exception as exc:
            future.cancel()
            raise DiscordBridgeError(f"Discord request failed: {exc}") from exc

    async def _channel(self, channel_id: int) -> Any:
        channel = self.client.get_channel(channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(channel_id)
        return channel

    async def _send(self, channel_id: int, text: str) -> int | None:
        channel = await self._channel(channel_id)
        message_id: int | None = None
        for chunk in _split_text(text):
            message = await channel.send(
                chunk, allowed_mentions=self._discord.AllowedMentions.none()
            )
            candidate = getattr(message, "id", None)
            if isinstance(candidate, int):
                message_id = candidate
        return message_id

    def send_message(self, channel_id: int, text: str) -> int | None:
        return self._submit(self._send(channel_id, text))

    async def _delete_message(self, channel_id: int, message_id: int) -> None:
        channel = await self._channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()

    def delete_message(self, channel_id: int, message_id: int) -> None:
        self._submit(self._delete_message(channel_id, message_id))

    async def _edit_message(self, channel_id: int, message_id: int, text: str) -> None:
        channel = await self._channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.edit(
            content=text[:DISCORD_TEXT_LIMIT],
            allowed_mentions=self._discord.AllowedMentions.none(),
        )

    def edit_message(self, channel_id: int, message_id: int, text: str) -> None:
        self._submit(self._edit_message(channel_id, message_id, text))

    async def _typing(self, channel_id: int) -> None:
        channel = await self._channel(channel_id)
        await channel.typing()

    def send_action(self, channel_id: int) -> None:
        self._submit(self._typing(channel_id))

    def close(self) -> None:
        loop = self._loop
        if loop and loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self.client.close(), loop)
                future.result(timeout=10)
            except Exception:
                LOG.warning("Discord bridge did not close cleanly")


class RelayClient:
    """Routes replies to Telegram or Discord while keeping the existing core API."""

    def __init__(self, telegram_client: Any, discord_bridge: DiscordBridge) -> None:
        self.telegram_client = telegram_client
        self.discord_bridge = discord_bridge
        self._capture = threading.local()

    @contextmanager
    def capture_messages(self) -> Any:
        previous = getattr(self._capture, "messages", None)
        messages: list[str] = []
        self._capture.messages = messages
        try:
            yield messages
        finally:
            if previous is None:
                del self._capture.messages
            else:
                self._capture.messages = previous

    def call(self, *args: Any, **kwargs: Any) -> Any:
        if self.telegram_client is None:
            raise DiscordBridgeError("Telegram is not configured")
        return self.telegram_client.call(*args, **kwargs)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> int | None:
        captured = getattr(self._capture, "messages", None)
        if captured is not None:
            captured.append(text)
            return None
        if chat_id < 0:
            return self.discord_bridge.send_message(-chat_id, text)
        if self.telegram_client is None:
            raise DiscordBridgeError("Telegram is not configured")
        return self.telegram_client.send_message(chat_id, text, reply_markup)

    def delete_message(self, chat_id: int, message_id: int) -> None:
        if chat_id < 0:
            self.discord_bridge.delete_message(-chat_id, message_id)
        else:
            if self.telegram_client is None:
                raise DiscordBridgeError("Telegram is not configured")
            self.telegram_client.delete_message(chat_id, message_id)

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        if chat_id < 0:
            self.discord_bridge.edit_message(-chat_id, message_id, text)
        else:
            if self.telegram_client is None:
                raise DiscordBridgeError("Telegram is not configured")
            self.telegram_client.edit_message(chat_id, message_id, text)

    def send_action(self, chat_id: int, action: str = "typing") -> None:
        if chat_id < 0:
            self.discord_bridge.send_action(-chat_id)
        else:
            if self.telegram_client is None:
                raise DiscordBridgeError("Telegram is not configured")
            self.telegram_client.send_action(chat_id, action)

    def download_photo(self, file_id: str, expected_size: int | None = None) -> Path:
        if not file_id.startswith("discord:"):
            if self.telegram_client is None:
                raise DiscordBridgeError("Telegram is not configured")
            return self.telegram_client.download_photo(file_id, expected_size)
        return self._download_discord_attachment(file_id, expected_size, "image")

    def download_attachment(
        self, file_id: str, expected_size: int | None = None, filename: str | None = None
    ) -> Path:
        if not file_id.startswith("discord:"):
            raise DiscordBridgeError("Only Discord attachments are supported")
        return self._download_discord_attachment(file_id, expected_size, "attachment", filename)

    @staticmethod
    def _download_discord_attachment(
        file_id: str,
        expected_size: int | None,
        label: str,
        filename: str | None = None,
    ) -> Path:
        max_size = 20 * 1024 * 1024
        if expected_size is not None and expected_size > max_size:
            raise DiscordBridgeError(f"Discord {label} exceeds 20MB")
        url = file_id.removeprefix("discord:")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in DISCORD_ATTACHMENT_HOSTS:
            raise DiscordBridgeError("Untrusted Discord attachment URL")
        request = urllib.request.Request(url, headers={"User-Agent": "telegram-codex-bot/1"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        too_large = int(content_length) > max_size
                    except ValueError:
                        too_large = False
                    if too_large:
                        raise DiscordBridgeError(f"Discord {label} exceeds 20MB")
                data = response.read(max_size + 1)
        except OSError as exc:
            raise DiscordBridgeError(f"Discord {label} download failed: {exc}") from exc
        if len(data) > max_size:
            raise DiscordBridgeError(f"Discord {label} exceeds 20MB")
        suffix = Path(filename or parsed.path).suffix[:20]
        with NamedTemporaryFile(prefix="codex-discord-", suffix=suffix, delete=False) as handle:
            handle.write(data)
            return Path(handle.name)
