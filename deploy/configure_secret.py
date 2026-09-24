#!/usr/bin/env python3
"""Interactively validate and install the root-only production environment file."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import secrets
import urllib.request


ENV_PATH = "/etc/telegram-codex-bot.env"
EXPECTED_USERNAME = "yeonwugptcodexbot"


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    token = getpass.getpass("Telegram bot token: ").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
        raise SystemExit("Invalid token format")

    with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getMe", timeout=20
    ) as response:
        result = json.load(response)
    username = result.get("result", {}).get("username", "")
    if not result.get("ok") or username.casefold() != EXPECTED_USERNAME.casefold():
        raise SystemExit("Token does not belong to the expected bot")

    pair_code = secrets.token_urlsafe(9)
    pair_hash = hashlib.sha256(pair_code.encode("utf-8")).hexdigest()
    content = "\n".join(
        [
            f"TELEGRAM_BOT_TOKEN={token}",
            f"TELEGRAM_PAIR_CODE_SHA256={pair_hash}",
            "CODEX_PROJECT_ROOT=/home/user/Raspberry_Pi",
            "BOT_STATE_FILE=/var/lib/telegram-codex-bot/state.json",
            "CODEX_BINARY=/usr/local/bin/codex",
            "CODEX_TIMEOUT_SECONDS=3600",
            "TELEGRAM_POLL_TIMEOUT_SECONDS=30",
            "LOG_LEVEL=INFO",
            "",
        ]
    )

    temp_path = f"{ENV_PATH}.tmp"
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, content.encode("utf-8"))
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temp_path, ENV_PATH)
    os.chown(ENV_PATH, 0, 0)
    os.chmod(ENV_PATH, 0o600)

    print(f"BOT_USERNAME=@{username}")
    print(f"PAIR_CODE={pair_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

