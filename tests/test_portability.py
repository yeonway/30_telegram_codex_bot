import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class PortableConfigurationTests(unittest.TestCase):
    def test_requires_at_least_one_chat_platform(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(app.ConfigError, "TELEGRAM_BOT_TOKEN"):
                app.Config.from_env()

    def test_env_file_is_data_not_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "SAFE=value with spaces\nDANGEROUS=$(touch should-not-run)\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                app.load_env_file(path)
                self.assertEqual(os.environ["SAFE"], "value with spaces")
                self.assertEqual(os.environ["DANGEROUS"], "$(touch should-not-run)")


class PortableRunnerTests(unittest.TestCase):
    def test_windows_runs_codex_without_setpriv(self):
        self.assertEqual(
            app._standard_command_head("codex.exe", platform_name="nt"),
            ["codex.exe"],
        )


if __name__ == "__main__":
    unittest.main()
