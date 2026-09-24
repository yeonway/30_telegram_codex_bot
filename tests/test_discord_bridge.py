import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import app
import discord_bridge
import discord_controls


class FakeCore:
    def __init__(self):
        self.updates = []

    def handle_update(self, update):
        self.updates.append(update)


class DiscordBridgeMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_unpaired_bridge_accepts_only_pairing_dm(self):
        core = FakeCore()
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge.application = core
        bridge.allowed_user_id = None
        bridge.allowed_channel_id = None
        message = SimpleNamespace(
            author=SimpleNamespace(id=123, bot=False),
            guild=None,
            channel=SimpleNamespace(id=456),
            content="!pair one-time-code",
            attachments=[],
        )

        await bridge._handle_message(message)

        self.assertEqual(core.updates[0]["message"]["text"], "/pair one-time-code")

    async def test_authorized_dm_maps_bang_command(self):
        core = FakeCore()
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge.application = core
        bridge.allowed_user_id = 123
        bridge.allowed_channel_id = None
        message = SimpleNamespace(
            author=SimpleNamespace(id=123, bot=False),
            guild=None,
            channel=SimpleNamespace(id=456),
            content="!status",
            attachments=[],
        )
        await bridge._handle_message(message)
        self.assertEqual(core.updates[0]["message"]["text"], "/status")
        self.assertEqual(core.updates[0]["message"]["chat"]["id"], -456)

    async def test_image_and_file_attachments_share_one_update(self):
        core = FakeCore()
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge.application = core
        bridge.allowed_user_id = 123
        bridge.allowed_channel_id = None
        message = SimpleNamespace(
            author=SimpleNamespace(id=123, bot=False),
            guild=None,
            channel=SimpleNamespace(id=456),
            content="둘 다 확인해줘",
            attachments=[
                SimpleNamespace(
                    content_type="image/png",
                    url="https://cdn.discordapp.com/image.png",
                    size=321,
                    filename="image.png",
                ),
                SimpleNamespace(
                    content_type="text/plain",
                    url="https://cdn.discordapp.com/report.txt",
                    size=654,
                    filename="report.txt",
                ),
            ],
        )

        await bridge._handle_message(message)

        update = core.updates[0]["message"]
        self.assertEqual(update["caption"], "둘 다 확인해줘")
        self.assertEqual(update["photo"][0]["file_size"], 321)
        self.assertEqual(update["attachment"][0]["file_name"], "report.txt")

    async def test_server_message_requires_configured_channel(self):
        core = FakeCore()
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge.application = core
        bridge.allowed_user_id = 123
        bridge.allowed_channel_id = None
        message = SimpleNamespace(
            author=SimpleNamespace(id=123, bot=False),
            guild=object(),
            channel=SimpleNamespace(id=456),
            content="hello",
            attachments=[],
        )
        await bridge._handle_message(message)
        self.assertEqual(core.updates, [])


class DiscordIntentTests(unittest.TestCase):
    def test_dm_only_does_not_request_privileged_message_content(self):
        fake_intents = SimpleNamespace(message_content=None)
        fake_discord = SimpleNamespace(
            Intents=SimpleNamespace(default=mock.Mock(return_value=fake_intents)),
            Client=mock.Mock(return_value=mock.Mock(event=lambda fn: fn)),
        )
        with mock.patch.dict("sys.modules", {"discord": fake_discord}):
            discord_bridge.DiscordBridge(mock.Mock(), "token", 123, None)
        self.assertFalse(fake_intents.message_content)

    def test_server_channel_requests_message_content_intent(self):
        fake_intents = SimpleNamespace(message_content=None)
        fake_discord = SimpleNamespace(
            Intents=SimpleNamespace(default=mock.Mock(return_value=fake_intents)),
            Client=mock.Mock(return_value=mock.Mock(event=lambda fn: fn)),
        )
        with mock.patch.dict("sys.modules", {"discord": fake_discord}):
            discord_bridge.DiscordBridge(mock.Mock(), "token", 123, 456)
        self.assertTrue(fake_intents.message_content)


class DiscordConfigTests(unittest.TestCase):
    def test_token_without_allowed_user_uses_pairing(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DISCORD_BOT_TOKEN": "secret",
                "BOT_PAIR_CODE_SHA256": "a" * 64,
                "DISCORD_ALLOWED_USER_ID": "",
                "CODEX_PROJECT_ROOT": "/projects",
            },
            clear=True,
        ), mock.patch.object(Path, "is_dir", return_value=True), mock.patch(
            "app.shutil.which", return_value="/usr/bin/codex"
        ):
            config = app.Config.from_env()

        self.assertIsNone(config.bot_token)
        self.assertEqual(config.discord_bot_token, "secret")
        self.assertIsNone(config.discord_allowed_user_id)


class DiscordDownloadTests(unittest.TestCase):
    def test_rejects_untrusted_attachment_host(self):
        relay = discord_bridge.RelayClient(mock.Mock(), mock.Mock())
        with self.assertRaisesRegex(discord_bridge.DiscordBridgeError, "Untrusted"):
            relay.download_photo("discord:https://example.com/image.png")


class DiscordTypingTests(unittest.IsolatedAsyncioTestCase):
    async def test_typing_uses_supported_messageable_api(self):
        bridge = object.__new__(discord_bridge.DiscordBridge)
        channel = mock.Mock()
        channel.typing.return_value = asyncio.sleep(0)
        bridge._channel = mock.AsyncMock(return_value=channel)

        await bridge._typing(456)

        bridge._channel.assert_awaited_once_with(456)
        channel.typing.assert_called_once_with()


class DiscordLifecycleTests(unittest.TestCase):
    def test_ready_gateway_must_still_have_a_live_worker(self):
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge._started = mock.Mock()
        bridge._started.wait.return_value = True
        bridge._thread = mock.Mock()
        bridge._thread.is_alive.return_value = False

        with self.assertRaisesRegex(discord_bridge.DiscordBridgeError, "not running"):
            bridge.wait_until_ready(timeout=0)

    def test_gateway_startup_timeout_is_reported(self):
        bridge = object.__new__(discord_bridge.DiscordBridge)
        bridge._started = mock.Mock()
        bridge._started.wait.return_value = False
        bridge._thread = mock.Mock()
        bridge._thread.is_alive.return_value = True

        with self.assertRaisesRegex(discord_bridge.DiscordBridgeError, "did not become ready"):
            bridge.wait_until_ready(timeout=0)


class DiscordControlAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_panel_view_rejects_other_channel_members(self):
        class FakeView:
            def __init__(self, timeout):
                self.timeout = timeout

        bridge = SimpleNamespace(
            allowed_user_id=7,
            application=mock.Mock(),
            _discord=SimpleNamespace(ui=SimpleNamespace(View=FakeView)),
        )
        controls = discord_controls.DiscordControls(bridge)
        view = controls._control_view()
        denied = SimpleNamespace(
            user=SimpleNamespace(id=8), response=SimpleNamespace(send_message=mock.AsyncMock())
        )
        allowed = SimpleNamespace(
            user=SimpleNamespace(id=7), response=SimpleNamespace(send_message=mock.AsyncMock())
        )

        self.assertFalse(await view.interaction_check(denied))
        denied.response.send_message.assert_awaited_once()
        self.assertTrue(await view.interaction_check(allowed))
        allowed.response.send_message.assert_not_awaited()


class RelayCaptureTests(unittest.TestCase):
    def test_captured_messages_are_not_sent_to_discord(self):
        discord = mock.Mock()
        relay = discord_bridge.RelayClient(mock.Mock(), discord)
        with relay.capture_messages() as messages:
            relay.send_message(-456, "권한 변경: safe")
        self.assertEqual(messages, ["권한 변경: safe"])
        discord.send_message.assert_not_called()

    def test_capture_is_thread_local_and_normal_send_resumes(self):
        discord = mock.Mock()
        relay = discord_bridge.RelayClient(mock.Mock(), discord)
        with relay.capture_messages():
            relay.send_message(-456, "captured")
        relay.send_message(-456, "visible")
        discord.send_message.assert_called_once_with(456, "visible")
