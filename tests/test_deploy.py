import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeployRestartTests(unittest.TestCase):
    def test_controlled_deploy_detaches_its_delayed_restart(self):
        script = (ROOT / "deploy" / "telegram-codex-deploy").read_text(encoding="utf-8")

        self.assertIn("systemd-run", script)
        self.assertIn("--no-block", script)
        self.assertIn("--on-active=45s", script)
        self.assertNotIn("\nsystemctl restart telegram-codex-bot.service", script)

    def test_project_catalog_verifier_bootstraps_repository_imports(self):
        script = (ROOT / "deploy" / "verify_project_catalog.py").read_text(encoding="utf-8")

        self.assertIn("sys.path.insert", script)
        self.assertIn("parents[1]", script)

    def test_root_prompt_warns_against_synchronous_self_restart(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("never synchronously restart", source)
        self.assertIn("detached delayed restart", source)


if __name__ == "__main__":
    unittest.main()
