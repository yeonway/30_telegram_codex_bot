import json
import unittest
from pathlib import Path
from unittest import mock

import app


class FakeTelegramClient:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


def authorized_bot():
    bot = object.__new__(app.BotApplication)
    bot.client = FakeTelegramClient()
    bot.state = mock.Mock()
    bot.state.snapshot.return_value = {
        "allowed_user_id": 100,
        "allowed_chat_id": 100,
    }
    bot._start_codex = mock.Mock()
    bot._handle_authorized = mock.Mock()
    return bot


def photo_update(caption_marker=object()):
    message = {
        "chat": {"id": 100, "type": "private"},
        "from": {"id": 100},
        "photo": [
            {"file_id": "small", "file_size": 100},
            {"file_id": "largest", "file_size": 500},
        ],
    }
    if isinstance(caption_marker, str):
        message["caption"] = caption_marker
    return {"update_id": 1, "message": message}


class TelegramImageMessageTests(unittest.TestCase):
    def test_photo_without_caption_waits_for_the_next_instruction(self):
        bot = authorized_bot()

        bot.handle_update(photo_update())

        bot._start_codex.assert_not_called()
        self.assertEqual(len(bot.client.messages), 1)
        self.assertIn("다음 메시지", bot.client.messages[0][1])
        bot.state.update.assert_called_once()

    def test_photo_caption_uses_largest_photo_and_caption_as_prompt(self):
        bot = authorized_bot()

        bot.handle_update(photo_update("  이 화면 오류를 고쳐줘  "))

        bot._start_codex.assert_called_once_with(
            100,
            "이 화면 오류를 고쳐줘",
            photo_file_id="largest",
            photo_size=500,
        )

    def test_unpaired_photo_cannot_pair_or_start_work(self):
        bot = authorized_bot()
        bot.state.snapshot.return_value = {
            "allowed_user_id": None,
            "allowed_chat_id": None,
        }

        bot.handle_update(photo_update("실행해"))

        bot._start_codex.assert_not_called()
        self.assertEqual(bot.client.messages, [])


class TelegramImageDownloadTests(unittest.TestCase):
    def test_declared_oversize_photo_is_rejected_before_api_call(self):
        client = app.TelegramClient("123456:abcdefghijklmnopqrstuvwxyz")
        client.call = mock.Mock()

        with self.assertRaisesRegex(app.TelegramError, "20MB"):
            client.download_photo("photo", app.MAX_IMAGE_BYTES + 1)

        client.call.assert_not_called()


class CodexImageCommandTests(unittest.TestCase):
    def make_config(self):
        return app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256="0" * 64,
            project_root=Path("/projects"),
            state_file=Path("/state.json"),
            codex_binary="codex",
        )

    def process(self):
        process = mock.Mock()
        process.communicate.return_value = (
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "ok"},
                }
            ),
            "",
        )
        process.returncode = 0
        process.poll.return_value = 0
        return process

    def test_image_flag_is_used_for_new_and_resumed_sessions(self):
        image = Path("/tmp/input.png")
        for session_id in (None, "session-id"):
            with self.subTest(session_id=session_id):
                process = self.process()
                with mock.patch("app.subprocess.Popen", return_value=process) as popen, mock.patch(
                    "app._standard_command_head", return_value=["codex"]
                ):
                    result = app.CodexRunner(self.make_config()).run(
                        Path("/projects/demo"), "inspect", session_id, image
                    )

                command = popen.call_args.args[0]
                image_index = command.index("-i")
                self.assertEqual(command[image_index + 1], str(image))
                if session_id:
                    self.assertEqual(
                        command[:4],
                        ["codex", "exec", "resume", "--json"],
                    )
                    self.assertNotIn("--color", command)
                self.assertEqual(result.text, "ok")


if __name__ == "__main__":
    unittest.main()
