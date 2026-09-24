import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import app


class FakeClient:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))
        return len(self.messages)


class UsageTests(unittest.TestCase):
    def test_parser_keeps_last_turn_usage(self):
        output = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "session"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "done"},
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 1200,
                            "cached_input_tokens": 800,
                            "output_tokens": 90,
                            "reasoning_output_tokens": 40,
                        },
                    }
                ),
            ]
        )

        result = app.parse_codex_jsonl(output)

        self.assertEqual(result.usage["input_tokens"], 1200)
        self.assertEqual(result.usage["output_tokens"], 90)

    def test_usage_message_is_explicit_about_missing_remaining_limit(self):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeClient()
        bot._usage_lock = mock.MagicMock()
        bot._usage_lock.__enter__.return_value = None
        bot._usage_lock.__exit__.return_value = None
        bot._last_usage = {
            "discord": {"input_tokens": 1200, "output_tokens": 90}
        }

        bot._send_usage(-10)

        message = bot.client.messages[-1][1]
        self.assertIn("입력 1,200", message)
        self.assertIn("남은 계정 한도", message)
        self.assertIn("제공하지 않음", message)


class FollowupQueueTests(unittest.TestCase):
    def test_running_session_queues_text_instead_of_rejecting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "demo"
            (project / ".git").mkdir(parents=True)
            bot = object.__new__(app.BotApplication)
            bot.client = FakeClient()
            bot.config = SimpleNamespace(max_concurrent_sessions=5)
            bot.projects = mock.Mock()
            bot.projects.resolve.return_value = project
            bot.runner = mock.Mock()
            bot.runner.is_running.return_value = True
            bot.state = mock.Mock()
            bot.state.current_session.return_value = "main"
            bot._ensure_current_project = mock.Mock(return_value="demo")
            bot._queue_lock = app.threading.RLock()
            bot._queued_prompts = {}

            bot._start_codex(-10, "테스트는 추가로 확인해줘")

            key = bot._run_key("demo", "main", "discord")
            self.assertEqual(bot._queued_prompts[key][0][1], "테스트는 추가로 확인해줘")
            self.assertIn("후속 지시 예약", bot.client.messages[-1][1])
            self.assertIn("실시간 주입 채널", bot.client.messages[-1][1])

    def test_queue_is_fifo(self):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeClient()
        bot._queue_lock = app.threading.RLock()
        bot._queued_prompts = {}

        bot._enqueue_prompt("run", 1, "first")
        bot._enqueue_prompt("run", 1, "second")

        self.assertEqual(bot._pop_queued_prompt("run"), (1, "first"))
        self.assertEqual(bot._pop_queued_prompt("run"), (1, "second"))
        self.assertIsNone(bot._pop_queued_prompt("run"))


if __name__ == "__main__":
    unittest.main()
