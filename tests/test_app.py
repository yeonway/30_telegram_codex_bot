import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import app


class StateStoreTests(unittest.TestCase):
    def test_state_persists_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = app.StateStore(path)
            store.update(allowed_user_id=123, current_project="demo")
            loaded = app.StateStore(path).snapshot()
            self.assertEqual(loaded["allowed_user_id"], 123)
            self.assertEqual(loaded["current_project"], "demo")
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_platform_contexts_keep_project_and_permission_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.update(context="telegram", current_project="telegram-project", permission="read")
            store.update(context="discord", current_project="discord-project", permission="safe")

            self.assertEqual(store.snapshot("telegram")["current_project"], "telegram-project")
            self.assertEqual(store.snapshot("telegram")["permission"], "read")
            self.assertEqual(store.snapshot("discord")["current_project"], "discord-project")
            self.assertEqual(store.snapshot("discord")["permission"], "safe")

    def test_one_shot_permission_is_consumed_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.update(context="discord", permission="full")
            barrier = threading.Barrier(3)
            results = []

            def consume() -> None:
                barrier.wait()
                results.append(store.consume_permission(context="discord"))

            workers = [threading.Thread(target=consume) for _ in range(2)]
            for worker in workers:
                worker.start()
            barrier.wait()
            for worker in workers:
                worker.join()

            self.assertCountEqual(results, ["full", "safe"])
            self.assertEqual(store.snapshot("discord")["permission"], "safe")

    def test_persistent_root_permission_is_not_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.update(context="discord", permission="root-always")

            self.assertEqual(
                store.consume_permission(context="discord"), "root-always"
            )
            self.assertEqual(
                store.consume_permission(context="discord"), "root-always"
            )

    def test_legacy_dangerous_or_transient_state_is_not_migrated_to_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "current_project": "legacy-project",
                        "permission": "full",
                        "sessions": {"legacy-project": {"main": "saved"}},
                        "current_sessions": {"legacy-project": "main"},
                        "pending_photo": {"file_id": "old"},
                    }
                ),
                encoding="utf-8",
            )

            store = app.StateStore(path)
            telegram = store.snapshot("telegram")
            discord = store.snapshot("discord")

            self.assertEqual(telegram["current_project"], "legacy-project")
            self.assertEqual(telegram["permission"], "safe")
            self.assertIsNone(telegram["pending_photo"])
            self.assertIsNone(discord["current_project"])
            self.assertEqual(discord["permission"], "safe")


class ProjectCatalogTests(unittest.TestCase):
    def test_only_immediate_git_projects_are_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good" / ".git").mkdir(parents=True)
            (root / "plain").mkdir()
            (root / ".hidden" / ".git").mkdir(parents=True)
            catalog = app.ProjectCatalog(root)
            self.assertEqual(catalog.list_projects(), ["good"])
            self.assertEqual(catalog.resolve("good"), (root / "good").resolve())
            with self.assertRaises(ValueError):
                catalog.resolve("../escape")

    def test_explicit_non_git_project_is_registered_without_opening_all_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zeta-chat-ui").mkdir()
            (root / "plain").mkdir()
            catalog = app.ProjectCatalog(root, ("zeta-chat-ui",))

            self.assertEqual(catalog.list_projects(), ["zeta-chat-ui"])
            self.assertEqual(
                catalog.resolve("zeta-chat-ui"), (root / "zeta-chat-ui").resolve()
            )
            with self.assertRaises(ValueError):
                catalog.resolve("plain")


class UtilityTests(unittest.TestCase):
    def test_sensitive_values_are_redacted(self):
        token = "123456:abcdefghijklmnopqrstuvwxyz"
        text = f"https://api.telegram.org/bot{token}/getMe Authorization: Bearer abc"
        result = app.sanitize(text, (token,))
        self.assertNotIn(token, result)
        self.assertNotIn("Bearer abc", result)

    def test_long_messages_are_split(self):
        chunks = app.split_message("a" * 9000)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= app.MESSAGE_CHUNK_SIZE for chunk in chunks))
        self.assertEqual("".join(chunks), "a" * 9000)

    def test_codex_jsonl_parser_uses_last_agent_message(self):
        output = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "abc"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "first"}}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "final"}}),
            ]
        )
        result = app.parse_codex_jsonl(output)
        self.assertEqual(result.session_id, "abc")
        self.assertEqual(result.text, "final")

    def test_telegram_message_attaches_menu_to_final_chunk(self):
        client = app.TelegramClient("123456:abcdefghijklmnopqrstuvwxyz")
        client.call = mock.Mock()
        markup = {"inline_keyboard": [[{"text": "메뉴", "callback_data": "tg:home"}]]}

        client.send_message(100, "hello", markup)

        payload = client.call.call_args.args[1]
        self.assertEqual(payload["reply_markup"], markup)


class FakeTelegramClient:
    def __init__(self):
        self.messages = []
        self.calls = []

    def call(self, method, payload=None, timeout=30):
        self.calls.append((method, payload, timeout))
        return None

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    def send_action(self, chat_id, action="typing"):
        return None


class BotPairingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "projects"
        (root / "30_telegram_codex_bot" / ".git").mkdir(parents=True)
        self.code = "SAFE-CODE"
        self.config = app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256=hashlib.sha256(self.code.encode()).hexdigest(),
            project_root=root,
            state_file=Path(self.temp.name) / "state" / "state.json",
            codex_binary=str(Path(self.temp.name) / "codex"),
        )
        Path(self.config.codex_binary).touch()
        self.client = FakeTelegramClient()
        self.bot = app.BotApplication(self.config, self.client)

    def tearDown(self):
        self.temp.cleanup()

    def update(self, user_id, text, chat_type="private"):
        return {
            "update_id": 1,
            "message": {
                "chat": {"id": user_id, "type": chat_type},
                "from": {"id": user_id},
                "text": text,
            },
        }

    def test_pairing_and_unauthorized_user_rejection(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        state = self.bot.state.snapshot("telegram")
        self.assertEqual(state["allowed_user_id"], 100)
        self.assertEqual(state["current_project"], "30_telegram_codex_bot")
        before = len(self.client.messages)
        self.bot.handle_update(self.update(200, "/status"))
        self.assertEqual(len(self.client.messages), before)

    def test_discord_can_pair_without_a_preconfigured_user_id(self):
        self.bot.handle_update(
            {
                "message": {
                    "_platform": "discord",
                    "chat": {"id": -456, "type": "private"},
                    "from": {"id": -123},
                    "text": f"/pair {self.code}",
                }
            }
        )

        state = self.bot.state.snapshot()
        self.assertEqual(state["discord_allowed_user_id"], 123)
        self.assertIn("페어링 완료", self.client.messages[-1][1])

    def test_wrong_pairing_code_does_not_claim_bot(self):
        self.bot.handle_update(self.update(100, "/pair WRONG"))
        self.assertIsNone(self.bot.state.snapshot()["allowed_user_id"])

    def test_group_pairing_is_ignored(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}", "group"))
        self.assertIsNone(self.bot.state.snapshot()["allowed_user_id"])

    def test_project_switch(self):
        (self.config.project_root / "other" / ".git").mkdir(parents=True)
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        self.bot.handle_update(self.update(100, "/use other"))
        self.assertEqual(self.bot.state.snapshot("telegram")["current_project"], "other")

    def callback(self, user_id, data):
        return {
            "update_id": 2,
            "callback_query": {
                "id": "callback-id",
                "from": {"id": user_id},
                "message": {
                    "message_id": 77,
                    "chat": {"id": user_id, "type": "private"},
                },
                "data": data,
            },
        }

    def test_telegram_menu_callback_switches_project(self):
        (self.config.project_root / "other" / ".git").mkdir(parents=True)
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        self.client.messages.clear()
        self.client.calls.clear()

        self.bot.handle_update(self.callback(100, "tg:projects"))

        self.assertEqual(self.client.calls[0][0], "answerCallbackQuery")
        self.assertEqual(self.client.calls[-1][0], "editMessageText")
        self.assertEqual(self.client.calls[-1][1]["message_id"], 77)
        markup = self.client.calls[-1][1]["reply_markup"]
        callbacks = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]
        self.assertIn("tg:project:1", callbacks)
        self.assertTrue(all(len(value.encode("utf-8")) <= 64 for value in callbacks))

        self.bot.handle_update(self.callback(100, "tg:project:1"))
        self.assertEqual(self.bot.state.snapshot("telegram")["current_project"], "other")

    def test_unauthorized_telegram_callback_is_ignored(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        before_messages = len(self.client.messages)
        before_calls = len(self.client.calls)

        self.bot.handle_update(self.callback(200, "tg:home"))

        self.assertEqual(len(self.client.messages), before_messages)
        self.assertEqual(len(self.client.calls), before_calls)

    def test_dangerous_telegram_permission_requires_confirmation(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        self.assertEqual(self.bot.state.snapshot("telegram")["permission"], "safe")

        self.bot.handle_update(self.callback(100, "tg:permission:full"))
        self.assertEqual(self.bot.state.snapshot("telegram")["permission"], "safe")

        self.bot.handle_update(self.callback(100, "tg:confirm:full"))
        self.assertEqual(self.bot.state.snapshot("telegram")["permission"], "full")

        self.bot.handle_update(self.callback(100, "tg:permission:safe"))
        self.assertEqual(self.bot.state.snapshot("telegram")["permission"], "safe")

    def test_telegram_session_buttons_collect_a_korean_name(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        self.bot.handle_update(self.callback(100, "tg:session:new"))
        self.bot.handle_update(self.update(100, "버그수정"))

        self.assertEqual(
            self.bot.state.current_session("30_telegram_codex_bot", context="telegram"),
            "버그수정",
        )

    def test_photo_can_be_sent_before_its_instruction(self):
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        photo = self.update(100, "")
        photo["message"].pop("text")
        photo["message"]["photo"] = [{"file_id": "image-id", "file_size": 321}]

        self.bot.handle_update(photo)
        with mock.patch.object(self.bot, "_start_codex") as start:
            self.bot.handle_update(self.update(100, "이 오류를 고쳐줘"))

        start.assert_called_once_with(
            100,
            "이 오류를 고쳐줘",
            photo_file_id="image-id",
            photo_size=321,
            attachments=None,
        )

    def test_pending_discord_image_and_file_are_consumed_together(self):
        self.bot.state.update(
            context="discord",
            pending_photo={"file_id": "discord:image", "file_size": 321},
            pending_attachment=[
                {
                    "file_id": "discord:file",
                    "file_size": 654,
                    "file_name": "report.txt",
                }
            ],
        )

        with mock.patch.object(self.bot, "_start_codex") as start:
            self.bot._handle_authorized(-456, "둘 다 확인해줘")

        start.assert_called_once_with(
            -456,
            "둘 다 확인해줘",
            photo_file_id="discord:image",
            photo_size=321,
            attachments=[
                {
                    "file_id": "discord:file",
                    "file_size": 654,
                    "file_name": "report.txt",
                }
            ],
        )
        state = self.bot.state.snapshot("discord")
        self.assertIsNone(state["pending_photo"])
        self.assertIsNone(state["pending_attachment"])

    def test_run_keys_are_isolated_per_platform(self):
        self.assertNotEqual(
            self.bot._run_key("30_telegram_codex_bot", "main", "telegram"),
            self.bot._run_key("30_telegram_codex_bot", "main", "discord"),
        )

    def test_telegram_delete_confirmation_keeps_its_original_session_target(self):
        project = "30_telegram_codex_bot"
        self.bot.handle_update(self.update(100, f"/pair {self.code}"))
        self.bot.handle_update(self.update(100, "/session new other"))
        self.bot.handle_update(self.update(100, "/session main"))
        self.bot.handle_update(self.callback(100, "tg:session:delete"))
        token = self.bot.state.snapshot("telegram")["pending_confirmation"]["token"]
        self.bot.handle_update(self.update(100, "/session other"))

        self.bot.handle_update(self.callback(100, f"tg:confirm:delete:{token}"))

        sessions = self.bot.state.list_sessions(project, context="telegram")
        self.assertNotIn("main", sessions)
        self.assertIn("other", sessions)


class DiscordStartupIsolationTests(unittest.TestCase):
    def test_discord_only_startup_never_calls_telegram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "projects"
            (root / "demo" / ".git").mkdir(parents=True)
            binary = Path(directory) / "codex"
            binary.touch()
            config = app.Config(
                bot_token=None,
                pair_code_sha256="0" * 64,
                project_root=root,
                state_file=Path(directory) / "state.json",
                codex_binary=str(binary),
                discord_bot_token="discord-token",
            )
            bot = app.BotApplication(config)
            bridge = mock.Mock()
            bridge.ensure_running.side_effect = bot._stopping.set
            relay = mock.Mock()
            with mock.patch("discord_bridge.DiscordBridge", return_value=bridge), mock.patch(
                "discord_bridge.RelayClient", return_value=relay
            ):
                bot.run()

            bridge.start.assert_called_once_with()
            bridge.wait_until_ready.assert_called_once_with()
            relay.call.assert_not_called()

    def test_telegram_startup_failure_does_not_take_down_ready_discord(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "projects"
            (root / "demo" / ".git").mkdir(parents=True)
            binary = Path(directory) / "codex"
            binary.touch()
            config = app.Config(
                bot_token="123456:abcdefghijklmnopqrstuvwxyz",
                pair_code_sha256="0" * 64,
                project_root=root,
                state_file=Path(directory) / "state.json",
                codex_binary=str(binary),
                discord_bot_token="discord-token",
                discord_allowed_user_id=123,
            )
            client = mock.Mock()
            bot = app.BotApplication(config, client)

            def telegram_offline(method, payload=None, timeout=30):
                bot._stopping.set()
                raise app.TelegramError("offline")

            client.call.side_effect = telegram_offline
            bridge = mock.Mock()
            with mock.patch("discord_bridge.DiscordBridge", return_value=bridge), mock.patch(
                "discord_bridge.RelayClient", side_effect=lambda telegram, discord: telegram
            ):
                bot.run()

            bridge.start.assert_called_once_with()
            bridge.wait_until_ready.assert_called_once_with()


class ShutdownSafetyTests(unittest.TestCase):
    def test_poll_result_is_not_processed_after_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "projects"
            (root / "demo" / ".git").mkdir(parents=True)
            binary = Path(directory) / "codex"
            binary.touch()
            config = app.Config(
                bot_token="123456:abcdefghijklmnopqrstuvwxyz",
                pair_code_sha256="0" * 64,
                project_root=root,
                state_file=Path(directory) / "state.json",
                codex_binary=str(binary),
            )
            client = mock.Mock()
            bot = app.BotApplication(config, client)

            def call(method, payload=None, timeout=30):
                if method == "getMe":
                    return {"username": "test"}
                if method == "getUpdates":
                    bot._stopping.set()
                    return [{"update_id": 1, "message": {}}]
                return None

            client.call.side_effect = call
            with mock.patch.object(bot, "handle_update") as handle_update:
                bot.run()

            handle_update.assert_not_called()

    def test_cancel_tolerates_process_exit_race(self):
        process = mock.Mock(pid=123)
        process.wait.side_effect = AssertionError("wait should not run")
        with mock.patch.object(app.os, "name", "posix"), mock.patch(
            "app.os.killpg", side_effect=ProcessLookupError, create=True
        ):
            app.CodexRunner._terminate_process(process)


class CodexRunnerTests(unittest.TestCase):
    def test_bot_secrets_are_removed_from_child_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            (project / ".git").mkdir(parents=True)
            binary = Path(directory) / "codex"
            binary.touch()
            config = app.Config(
                bot_token="123456:abcdefghijklmnopqrstuvwxyz",
                pair_code_sha256="0" * 64,
                project_root=Path(directory),
                state_file=Path(directory) / "state.json",
                codex_binary=str(binary),
            )
            process = mock.Mock()
            process.communicate.return_value = (
                json.dumps({"type": "thread.started", "thread_id": "session"})
                + "\n"
                + json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
                "",
            )
            process.returncode = 0
            process.poll.return_value = 0
            with mock.patch.dict(
                os.environ,
                {
                    "TELEGRAM_BOT_TOKEN": "secret",
                    "TELEGRAM_PAIR_CODE_SHA256": "hash",
                    "DISCORD_BOT_TOKEN": "discord-secret",
                    "DISCORD_ALLOWED_USER_ID": "123",
                    "DISCORD_ALLOWED_CHANNEL_ID": "456",
                },
            ), mock.patch("app.subprocess.Popen", return_value=process) as popen:
                result = app.CodexRunner(config).run(project, "hello", None)
            child_env = popen.call_args.kwargs["env"]
            self.assertNotIn("TELEGRAM_BOT_TOKEN", child_env)
            self.assertNotIn("TELEGRAM_PAIR_CODE_SHA256", child_env)
            self.assertNotIn("DISCORD_BOT_TOKEN", child_env)
            self.assertNotIn("DISCORD_ALLOWED_USER_ID", child_env)
            self.assertNotIn("DISCORD_ALLOWED_CHANNEL_ID", child_env)
            self.assertEqual(result.text, "ok")

class RootOneShotTests(unittest.TestCase):
    def test_root_grant_is_consumed_before_worker_starts(self):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeTelegramClient()
        bot.config = mock.Mock(max_concurrent_sessions=5)
        bot.projects = mock.Mock()
        bot.projects.resolve.return_value = Path("/projects/demo")
        bot.runner = mock.Mock()
        bot.runner.is_running.return_value = False
        bot.runner.at_capacity.return_value = False
        bot.state = mock.Mock()
        bot.state.current_session.return_value = "main"
        bot.state.snapshot.return_value = {
            "sessions": {"demo": {"main": "saved-session"}},
            "model": "gpt-5.6-sol",
            "intelligence": "high",
            "permission": "root",
        }
        bot.state.consume_permission.return_value = "root"
        bot._ensure_current_project = mock.Mock(return_value="demo")

        with mock.patch("app.threading.Thread") as thread:
            bot._start_codex(100, "inspect root")

        bot.state.consume_permission.assert_called_once_with(context="telegram")
        worker_args = thread.call_args.kwargs["args"]
        self.assertIsNone(worker_args[3])
        self.assertEqual(worker_args[7], "root")
        thread.return_value.start.assert_called_once_with()
        self.assertIn("Codex 실행 준비", bot.client.messages[-1][1])

    def test_full_grant_is_consumed_before_worker_starts(self):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeTelegramClient()
        bot.config = mock.Mock(max_concurrent_sessions=5)
        bot.projects = mock.Mock()
        bot.projects.resolve.return_value = Path("/projects/demo")
        bot.runner = mock.Mock()
        bot.runner.is_running.return_value = False
        bot.runner.at_capacity.return_value = False
        bot.state = mock.Mock()
        bot.state.current_session.return_value = "main"
        bot.state.snapshot.return_value = {
            "sessions": {"demo": {"main": "saved-session"}},
            "model": "gpt-5.6-sol",
            "intelligence": "high",
            "permission": "full",
        }
        bot.state.consume_permission.return_value = "full"
        bot._ensure_current_project = mock.Mock(return_value="demo")

        with mock.patch("app.threading.Thread") as thread:
            bot._start_codex(100, "inspect full")

        bot.state.consume_permission.assert_called_once_with(context="telegram")
        worker_args = thread.call_args.kwargs["args"]
        self.assertEqual(worker_args[3], "saved-session")
        self.assertEqual(worker_args[7], "full")
        self.assertIn("Codex 실행 준비", bot.client.messages[-1][1])

if __name__ == "__main__":
    unittest.main()
