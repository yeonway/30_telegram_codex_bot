import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import app
from codex_progress import CodexProgress


class ProgressRenderingTests(unittest.TestCase):
    def make_progress(self):
        now = [100.0]
        progress = CodexProgress(started_at=100.0, clock=lambda: now[0])
        return progress, now

    def test_public_reasoning_and_actions_accumulate_in_one_message(self):
        progress, now = self.make_progress()
        progress.apply_event(
            {
                "type": "item.completed",
                "item": {"type": "reasoning", "text": "파일 구조를 먼저 확인합니다."},
            }
        )
        progress.apply_event(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "python -m unittest"},
            }
        )
        now[0] = 114.0

        rendered = progress.render()

        self.assertIn("🧠 작업 중", rendered)
        self.assertIn("파일 구조를 먼저 확인합니다.", rendered)
        self.assertIn("→ 테스트 실행", rendered)
        self.assertIn("14초", rendered)

    def test_hidden_or_raw_reasoning_is_never_rendered(self):
        progress, _ = self.make_progress()
        progress.apply_event(
            {
                "type": "item.completed",
                "item": {
                    "type": "reasoning",
                    "raw_content": "hidden chain of thought",
                    "encrypted_content": "secret ciphertext",
                },
            }
        )

        rendered = progress.render()

        self.assertNotIn("hidden chain", rendered)
        self.assertNotIn("ciphertext", rendered)

    def test_final_message_keeps_steps_and_total_time(self):
        progress, now = self.make_progress()
        progress.add_step("파일 수정")
        now[0] = 121.4

        rendered = progress.render("success")

        self.assertIn("✅ 작업 완료", rendered)
        self.assertIn("파일 수정", rendered)
        self.assertIn("총 소요 시간: 21.4초", rendered)


class StreamingRunnerTests(unittest.TestCase):
    def test_jsonl_events_are_delivered_before_final_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            config = app.Config(
                bot_token="123456:abcdefghijklmnopqrstuvwxyz",
                pair_code_sha256="0" * 64,
                project_root=Path(directory),
                state_file=Path(directory) / "state.json",
                codex_binary=sys.executable,
                codex_timeout_seconds=60,
            )
            runner = app.CodexRunner(config)
            event = {
                "type": "item.completed",
                "item": {"type": "reasoning", "text": "코드 분석"},
            }
            process = subprocess.Popen(
                [sys.executable, "-c", f"print({json.dumps(json.dumps(event))})"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            received = []

            stdout, stderr = runner._communicate_streaming(
                process, "prompt", received.append
            )

            self.assertEqual(received, [event])
            self.assertIn("item.completed", stdout)
            self.assertEqual(stderr, "")


class ProgressLifecycleTests(unittest.TestCase):
    def test_worker_keeps_final_answer_and_edits_progress_in_place(self):
        class Client:
            def __init__(self):
                self.sent = []
                self.edited = []
                self.deleted = []

            def send_action(self, _chat_id):
                pass

            def send_message(self, chat_id, text):
                self.sent.append((chat_id, text))

            def edit_message(self, chat_id, message_id, text):
                self.edited.append((chat_id, message_id, text))

            def delete_message(self, chat_id, message_id):
                self.deleted.append((chat_id, message_id))

        class Runner:
            def run(self, *args, **kwargs):
                callback = kwargs["progress_callback"]
                callback(
                    {
                        "type": "item.completed",
                        "item": {"type": "reasoning", "text": "코드 분석"},
                    }
                )
                return app.CodexResult("최종 답변", "session-id")

        bot = object.__new__(app.BotApplication)
        bot.client = Client()
        bot.runner = Runner()
        bot.state = mock.Mock()
        bot.config = SimpleNamespace(bot_token="not-a-real-token")
        progress = CodexProgress()

        bot._codex_worker(
            100,
            Path("/projects/demo"),
            "작업",
            None,
            None,
            None,
            None,
            "safe",
            None,
            "main",
            "telegram:demo:main",
            "telegram",
            77,
            progress,
        )

        self.assertIn("최종 답변", bot.client.sent[-1][1])
        self.assertIn("✅ 작업 완료", bot.client.edited[-1][2])
        self.assertIn("코드 분석", bot.client.edited[-1][2])
        self.assertEqual(bot.client.deleted, [])


if __name__ == "__main__":
    unittest.main()
