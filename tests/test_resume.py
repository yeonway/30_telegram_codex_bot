import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class ResumeCommandTests(unittest.TestCase):
    def test_resume_uses_only_supported_options(self):
        root = Path(__file__).resolve().parents[1]
        project = Path(tempfile.mkdtemp(dir=root))
        self.addCleanup(shutil.rmtree, project, True)
        (project / ".git").mkdir()
        binary = project / "codex"
        binary.touch()
        config = app.Config(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            pair_code_sha256="0" * 64,
            project_root=root,
            state_file=project / "state.json",
            codex_binary=str(binary),
        )
        process = mock.Mock()
        process.communicate.return_value = (
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "resumed"},
                }
            ),
            "",
        )
        process.returncode = 0
        process.poll.return_value = 0

        with mock.patch("app.subprocess.Popen", return_value=process) as popen, mock.patch(
            "app._standard_command_head", return_value=[str(binary)]
        ):
            result = app.CodexRunner(config).run(project, "follow up", "session-id")

        command = popen.call_args.args[0]
        self.assertEqual(
            command[:4],
            [str(binary), "exec", "resume", "--json"],
        )
        self.assertIn('sandbox_mode="workspace-write"', command)
        self.assertIn('approval_policy="never"', command)
        self.assertEqual(command[-2:], ["session-id", "-"])
        self.assertNotIn("--color", command)
        self.assertEqual(result.text, "resumed")


if __name__ == "__main__":
    unittest.main()
