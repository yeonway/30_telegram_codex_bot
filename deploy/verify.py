#!/usr/bin/env python3
"""Production verification that checks Telegram and performs a real Codex turn."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    codex_binary = os.environ.get("CODEX_BINARY", "/usr/local/bin/codex")
    project = Path("/home/user/Raspberry_Pi/30_telegram_codex_bot")

    with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getMe", timeout=20
    ) as response:
        telegram = json.load(response)

    child_env = os.environ.copy()
    child_env.pop("TELEGRAM_BOT_TOKEN", None)
    child_env.pop("TELEGRAM_PAIR_CODE_SHA256", None)
    child_env.pop("DISCORD_BOT_TOKEN", None)
    child_env.pop("DISCORD_ALLOWED_USER_ID", None)
    child_env.pop("DISCORD_ALLOWED_CHANNEL_ID", None)
    smoke = subprocess.run(
        [
            codex_binary,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-C",
            str(project),
            "Reply with exactly TELEGRAM_CODEX_SMOKE_OK and nothing else.",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=240,
        env=child_env,
        check=False,
    )
    codex_ok = smoke.returncode == 0 and smoke.stdout.strip() == "TELEGRAM_CODEX_SMOKE_OK"
    result = {
        "ok": bool(telegram.get("ok")) and codex_ok,
        "bot_username": telegram.get("result", {}).get("username"),
        "codex_exec_smoke_ok": codex_ok,
        "codex_exit_code": smoke.returncode,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
