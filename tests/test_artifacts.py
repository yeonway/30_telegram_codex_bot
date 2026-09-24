import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import artifact_delivery


class ArtifactManifestTests(unittest.TestCase):
    def test_loads_confined_release_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Path(directory)
            artifact = outbox / "app.apk"
            artifact.write_bytes(b"apk")
            (outbox / "artifacts.json").write_text(
                json.dumps(
                    [
                        {
                            "path": "app.apk",
                            "title": "JARVIS 1.2.6",
                            "description": "external test",
                            "publish_as": "release",
                            "app_name": "JARVIS",
                            "version": "1.2.6",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            requests = artifact_delivery.load_artifact_requests(outbox)

            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].path, artifact.resolve())
            self.assertEqual(requests[0].publish_as, "release")

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Path(directory) / "outbox"
            outbox.mkdir()
            outside = Path(directory) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            (outbox / "artifacts.json").write_text(
                json.dumps([{"path": "../secret.txt", "title": "bad"}]),
                encoding="utf-8",
            )

            with self.assertRaises(artifact_delivery.ArtifactError):
                artifact_delivery.load_artifact_requests(outbox)

    def test_release_requires_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Path(directory)
            (outbox / "app.apk").write_bytes(b"apk")
            (outbox / "artifacts.json").write_text(
                json.dumps(
                    [
                        {
                            "path": "app.apk",
                            "title": "app",
                            "publish_as": "release",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(artifact_delivery.ArtifactError):
                artifact_delivery.load_artifact_requests(outbox)


class ArtifactPublisherClientTests(unittest.TestCase):
    def test_publisher_is_invoked_without_shell(self):
        request = artifact_delivery.ArtifactRequest(
            path=Path("/tmp/app.apk"),
            title="JARVIS",
            description="test",
            publish_as="release",
            app_name="JARVIS",
            version="1.2.6",
        )
        response = {
            "title": "JARVIS",
            "type": "APK",
            "size": 1024,
            "sha256": "a" * 64,
            "url": "https://drive.dcout.cloud/downloads/jarvis.apk",
        }
        completed = mock.Mock(returncode=0, stdout=json.dumps(response), stderr="")

        with mock.patch("artifact_delivery.subprocess.run", return_value=completed) as run:
            result = artifact_delivery.publish_artifacts([request])

        self.assertEqual(result, [response])
        self.assertNotIn("shell", run.call_args.kwargs)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/sudo", "-n", artifact_delivery.PUBLISHER])
        self.assertIn("--app-name", command)

    def test_download_card_is_platform_neutral(self):
        card = artifact_delivery.render_artifact_cards(
            [
                {
                    "title": "JARVIS 1.2.6",
                    "type": "APK",
                    "size": 2 * 1024 * 1024,
                    "sha256": "abcdef1234567890",
                    "url": "https://drive.dcout.cloud/downloads/jarvis.apk",
                }
            ]
        )

        self.assertIn("📦 JARVIS 1.2.6", card)
        self.assertIn("APK · 2.0 MB", card)
        self.assertIn("abcdef123456…", card)
        self.assertIn("⬇️ https://drive.dcout.cloud/", card)


class DeploymentContractTests(unittest.TestCase):
    def test_deploy_installs_android_and_artifact_helpers(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "deploy" / "install.sh").read_text(encoding="utf-8")
        delayed = (root / "deploy" / "telegram-codex-deploy").read_text(
            encoding="utf-8"
        )
        sudoers = (root / "deploy" / "telegram-codex-bot.sudoers").read_text(
            encoding="utf-8"
        )

        for script in (install, delayed):
            self.assertIn("artifact_delivery.py", script)
            self.assertIn("telegram-codex-publish-artifact", script)
            self.assertIn("android-build-apk", script)
            self.assertIn("/var/cache/telegram-codex-bot/gradle", script)
        self.assertIn("telegram-codex-publish-artifact *", sudoers)


if __name__ == "__main__":
    unittest.main()
