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


class ModelAndPermissionCommandTests(unittest.TestCase):
    def make_bot(self):
        bot = object.__new__(app.BotApplication)
        bot.client = FakeTelegramClient()
        bot.state = mock.Mock()
        bot.state.snapshot.return_value = {"model": None, "permission": "safe"}
        bot.runner = mock.Mock()
        bot.runner.is_running.return_value = False
        bot._available_models = mock.Mock(
            return_value=["gpt-5.4", "gpt-5.5", "gpt-5.6-sol"]
        )
        bot._available_intelligence_levels = mock.Mock(
            return_value=["low", "medium", "high", "xhigh", "max", "ultra"]
        )
        return bot

    def test_model_can_be_selected_and_reset(self):
        bot = self.make_bot()

        bot._select_model(100, "gpt-5.6-sol")
        bot.state.update.assert_called_with(context="telegram", model="gpt-5.6-sol")
        self.assertIn("gpt-5.6-sol", bot.client.messages[-1][1])

        bot.state.update.reset_mock()
        bot._select_model(100, "default")
        bot.state.update.assert_called_with(context="telegram", model=None)

    def test_unavailable_model_is_rejected(self):
        bot = self.make_bot()

        bot._select_model(100, "gpt-does-not-exist")

        bot.state.update.assert_not_called()
        self.assertIn("사용할 수 없는 모델", bot.client.messages[-1][1])

    def test_permission_modes_can_be_selected(self):
        for permission in ("read", "safe", "auto"):
            with self.subTest(permission=permission):
                bot = self.make_bot()
                bot._select_permission(100, permission)
                bot.state.update.assert_called_once_with(context="telegram", permission=permission)

        bot = self.make_bot()
        bot._select_permission(100, "full")
        bot.state.update.assert_not_called()
        self.assertIn("full confirm", bot.client.messages[-1][1])

    def test_root_permission_requires_exact_confirmation(self):
        bot = self.make_bot()

        bot._select_permission(100, "root")
        bot.state.update.assert_not_called()
        self.assertIn("root confirm", bot.client.messages[-1][1])

        bot._select_permission(100, "root confirm")
        bot.state.update.assert_called_once_with(context="telegram", permission="root")
        self.assertIn("다음 작업 1회", bot.client.messages[-1][1])

    def test_intelligence_can_be_selected_and_reset(self):
        bot = self.make_bot()

        bot._select_intelligence(100, "xhigh")
        bot.state.update.assert_called_with(context="telegram", intelligence="xhigh")

        bot.state.update.reset_mock()
        bot._select_intelligence(100, "default")
        bot.state.update.assert_called_with(context="telegram", intelligence=None)

    def test_unsupported_intelligence_is_rejected(self):
        bot = self.make_bot()

        bot._select_intelligence(100, "impossible")

        bot.state.update.assert_not_called()
        self.assertIn("지원하지 않는 단계", bot.client.messages[-1][1])

    def test_model_and_permission_can_be_staged_for_the_next_work(self):
        bot = self.make_bot()
        bot.runner.is_running.return_value = True

        bot._select_model(100, "gpt-5.6-sol")
        bot._select_intelligence(100, "high")
        bot._select_permission(100, "full confirm")

        self.assertEqual(bot.state.update.call_count, 3)


class CodexControlOptionTests(unittest.TestCase):
    @staticmethod
    def config():
        return app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256="0" * 64,
            project_root=Path("/projects"),
            state_file=Path("/state.json"),
            codex_binary="codex",
        )

    @staticmethod
    def process():
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

    def command_for(self, session_id, permission, intelligence="high"):
        process = self.process()
        with mock.patch("app.subprocess.Popen", return_value=process) as popen, mock.patch(
            "app._root_command_head",
            return_value=["/usr/bin/sudo", "-n", app.ROOT_RUNNER],
        ):
            app.CodexRunner(self.config()).run(
                Path("/projects/demo"),
                "inspect",
                session_id,
                model="gpt-5.6-sol",
                permission=permission,
                intelligence=intelligence,
            )
        return popen.call_args.args[0], process.communicate.call_args.args[0]

    def test_model_and_safe_sandbox_are_passed_to_new_and_resume(self):
        for session_id in (None, "session-id"):
            with self.subTest(session_id=session_id):
                command, prompt = self.command_for(session_id, "safe")
                self.assertIn("codex", command)
                self.assertIn("exec", command)
                model_index = command.index("-m")
                self.assertEqual(command[model_index + 1], "gpt-5.6-sol")
                self.assertIn('model_reasoning_effort="high"', command)
                self.assertIn('approval_policy="never"', command)
                if session_id:
                    self.assertIn('sandbox_mode="workspace-write"', command)
                else:
                    sandbox_index = command.index("--sandbox")
                    self.assertEqual(command[sandbox_index + 1], "workspace-write")
                self.assertIn("Work only inside the selected project", prompt)

    def test_read_permission_is_explicit_for_new_and_resume(self):
        for session_id in (None, "session-id"):
            with self.subTest(session_id=session_id):
                command, prompt = self.command_for(session_id, "read")
                if session_id:
                    self.assertIn('sandbox_mode="read-only"', command)
                else:
                    sandbox_index = command.index("--sandbox")
                    self.assertEqual(command[sandbox_index + 1], "read-only")
                self.assertIn("Read-only access is selected", prompt)

    def test_full_permission_bypasses_sandbox_for_new_and_resume(self):
        for session_id in (None, "session-id"):
            with self.subTest(session_id=session_id):
                command, prompt = self.command_for(session_id, "full")
                self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
                self.assertNotIn("--sandbox", command)
                self.assertIn("explicitly selected", prompt)

    def test_root_permission_uses_sudo_ephemeral_and_never_resumes(self):
        command, prompt = self.command_for("existing-session", "root")
        self.assertEqual(
            command[:3],
            ["/usr/bin/sudo", "-n", app.ROOT_RUNNER],
        )
        self.assertIn("--ephemeral", command)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertNotIn("resume", command)
        self.assertNotIn("existing-session", command)
        self.assertIn("One-shot root access", prompt)

    def test_persistent_root_permission_resumes_its_saved_session(self):
        command, prompt = self.command_for("existing-session", "root-always")
        self.assertEqual(
            command[:3],
            ["/usr/bin/sudo", "-n", app.ROOT_RUNNER],
        )
        self.assertNotIn("--ephemeral", command)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertIn("resume", command)
        self.assertIn("existing-session", command)
        self.assertIn("Persistent root mode", prompt)

    def test_persistent_root_new_session_is_saved_not_ephemeral(self):
        command, _ = self.command_for(None, "root-always")
        self.assertNotIn("resume", command)
        self.assertNotIn("--ephemeral", command)

    def test_auto_permission_uses_on_request_auto_reviewer(self):
        for session_id in (None, "session-id"):
            with self.subTest(session_id=session_id):
                command, prompt = self.command_for(session_id, "auto")
                self.assertIn('approval_policy="on-request"', command)
                self.assertIn('approvals_reviewer="auto_review"', command)
                self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
                if session_id:
                    self.assertIn('sandbox_mode="workspace-write"', command)
                else:
                    sandbox_index = command.index("--sandbox")
                    self.assertEqual(command[sandbox_index + 1], "workspace-write")
                self.assertIn("Auto-review permission is selected", prompt)


if __name__ == "__main__":
    unittest.main()
