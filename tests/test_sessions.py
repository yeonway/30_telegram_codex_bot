import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import app


class FakeTelegramClient:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class StateSessionTests(unittest.TestCase):
    def test_legacy_project_session_is_migrated_to_main(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "current_project": "demo",
                        "sessions": {"demo": "legacy-session-id"},
                    }
                ),
                encoding="utf-8",
            )

            store = app.StateStore(path)

            self.assertEqual(store.current_session("demo"), "main")
            self.assertEqual(store.list_sessions("demo"), {"main": "legacy-session-id"})

    def test_named_sessions_keep_independent_codex_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.ensure_session("demo")
            self.assertTrue(store.create_session("demo", "backend"))
            store.set_session("demo", "main", "main-id")
            store.set_session("demo", "backend", "backend-id")

            self.assertEqual(
                store.list_sessions("demo"),
                {"main": "main-id", "backend": "backend-id"},
            )
            self.assertEqual(store.current_session("demo"), "backend")
            self.assertTrue(store.select_session("demo", "main"))
            self.assertEqual(store.current_session("demo"), "main")

    def test_discord_root_sessions_persist_separately_from_regular_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = app.StateStore(path)
            store.ensure_session("demo", context="discord")
            store.set_session(
                "demo", "main", "regular-id", context="discord"
            )
            store.set_session(
                "demo", "main", "root-id", context="discord", root=True
            )

            reloaded = app.StateStore(path)

            self.assertEqual(
                reloaded.session_id("demo", "main", context="discord"),
                "regular-id",
            )
            self.assertEqual(
                reloaded.session_id(
                    "demo", "main", context="discord", root=True
                ),
                "root-id",
            )

    def test_session_lifecycle_keeps_root_session_slots_in_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.ensure_session("demo", context="discord")
            store.set_session(
                "demo", "main", "root-id", context="discord", root=True
            )

            self.assertTrue(
                store.rename_session("demo", "main", "work", context="discord")
            )
            self.assertEqual(
                store.session_id("demo", "work", context="discord", root=True),
                "root-id",
            )
            store.set_session(
                "demo", "work", None, context="discord", both=True
            )
            self.assertIsNone(
                store.session_id("demo", "work", context="discord", root=True)
            )
            self.assertTrue(store.delete_session("demo", "work", context="discord"))
            self.assertIsNone(
                store.session_id("demo", "main", context="discord", root=True)
            )

    def test_recent_session_list_is_limited_to_ten_and_moves_on_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.ensure_session("demo")
            for index in range(12):
                self.assertTrue(store.create_session("demo", f"work-{index}"))

            recent = list(store.list_sessions("demo", limit=10))
            self.assertEqual(recent[0], "work-11")
            self.assertEqual(recent[-1], "work-2")
            self.assertNotIn("main", recent)

            self.assertTrue(store.select_session("demo", "work-3"))
            self.assertEqual(next(iter(store.list_sessions("demo", limit=10))), "work-3")

    def test_rename_preserves_codex_id_and_current_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.ensure_session("demo")
            store.set_session("demo", "main", "saved-id")

            self.assertTrue(store.rename_session("demo", "main", "renamed"))
            self.assertEqual(store.current_session("demo"), "renamed")
            self.assertEqual(store.list_sessions("demo"), {"renamed": "saved-id"})

    def test_delete_current_selects_remaining_and_last_creates_main(self):
        with tempfile.TemporaryDirectory() as directory:
            store = app.StateStore(Path(directory) / "state.json")
            store.ensure_session("demo")
            store.create_session("demo", "backend")

            self.assertTrue(store.delete_session("demo", "backend"))
            self.assertEqual(store.current_session("demo"), "main")
            self.assertTrue(store.delete_session("demo", "main"))
            self.assertEqual(store.list_sessions("demo"), {"main": None})


class SessionCommandTests(unittest.TestCase):
    def make_bot(self, state_path):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeTelegramClient()
        bot.state = app.StateStore(state_path)
        bot.state.ensure_session("demo")
        bot.runner = mock.Mock()
        bot.runner.status.return_value = []
        bot.runner.is_running.return_value = False
        bot.config = SimpleNamespace(max_concurrent_sessions=3)
        bot._ensure_current_project = mock.Mock(return_value="demo")
        return bot

    def test_create_and_switch_named_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = self.make_bot(Path(directory) / "state.json")

            bot._handle_session_command(100, "new backend")
            self.assertEqual(bot.state.current_session("demo", context="telegram"), "backend")
            bot._handle_session_command(100, "main")
            self.assertEqual(bot.state.current_session("demo", context="telegram"), "main")

    def test_session_list_marks_selected_and_running_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = self.make_bot(Path(directory) / "state.json")
            bot.state.create_session("demo", "backend")
            bot.runner.status.return_value = [
                {
                    "key": bot._run_key("demo", "main"),
                    "label": "demo/main",
                    "project": "demo",
                    "elapsed": 12,
                }
            ]

            bot._send_sessions(100)

            message = bot.client.messages[-1][1]
            self.assertIn("main · 실행 중 12초", message)
            self.assertIn("▶ backend", message)

    def test_rename_and_confirmed_delete_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = self.make_bot(Path(directory) / "state.json")
            bot.state.set_session("demo", "main", "saved-id")

            bot._handle_session_command(100, "rename work")
            self.assertEqual(bot.state.current_session("demo", context="telegram"), "work")
            self.assertEqual(bot.state.list_sessions("demo", context="telegram"), {"work": "saved-id"})

            bot._handle_session_command(100, "delete work")
            self.assertIn("confirm", bot.client.messages[-1][1])
            self.assertIn("work", bot.state.list_sessions("demo", context="telegram"))

            bot._handle_session_command(100, "delete work confirm")
            self.assertEqual(bot.state.list_sessions("demo", context="telegram"), {"main": None})

    def test_running_session_cannot_be_renamed_or_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = self.make_bot(Path(directory) / "state.json")
            bot.runner.is_running.return_value = True

            bot._handle_session_command(100, "rename blocked")
            self.assertIn("실행 중", bot.client.messages[-1][1])
            bot._handle_session_command(100, "delete main confirm")
            self.assertIn("실행 중", bot.client.messages[-1][1])
            self.assertIn("main", bot.state.list_sessions("demo"))


class BlockingProcess:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.returncode = 0
        self.pid = 999999

    def communicate(self, _prompt, timeout=None):
        self.started.set()
        if not self.release.wait(timeout=5):
            raise AssertionError("test process was not released")
        output = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "ok"},
            }
        )
        return output, ""

    def poll(self):
        return 0 if self.release.is_set() else None


class ConcurrentRunnerTests(unittest.TestCase):
    def test_default_concurrent_session_limit_is_five(self):
        config = app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256="0" * 64,
            project_root=Path("/projects"),
            state_file=Path("/state.json"),
        )
        self.assertEqual(config.max_concurrent_sessions, 5)

    def test_distinct_sessions_run_together_with_per_session_lock_and_limit(self):
        config = app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256="0" * 64,
            project_root=Path("/projects"),
            state_file=Path("/state.json"),
            codex_binary="codex",
            max_concurrent_sessions=5,
        )
        runner = app.CodexRunner(config)
        processes = [BlockingProcess() for _ in range(5)]
        errors = []

        def run(key, label):
            try:
                runner.run(
                    Path("/projects/demo"),
                    "work",
                    None,
                    run_key=key,
                    run_label=label,
                )
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        with mock.patch("app.subprocess.Popen", side_effect=processes):
            threads = [
                threading.Thread(
                    target=run,
                    args=(f"demo-session-{index}", f"demo/session-{index}"),
                )
                for index in range(5)
            ]
            for thread, process in zip(threads, processes):
                thread.start()
                self.assertTrue(process.started.wait(timeout=2))

            self.assertEqual(len(runner.status()), 5)
            with self.assertRaisesRegex(app.CodexRunError, "현재 세션"):
                runner.run(
                    Path("/projects/demo"), "again", None, run_key="demo-session-0"
                )
            with self.assertRaisesRegex(app.CodexRunError, "동시 실행 한도"):
                runner.run(Path("/projects/demo"), "sixth", None, run_key="demo-session-5")

            for process in processes:
                process.release.set()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(runner.status(), [])


if __name__ == "__main__":
    unittest.main()
