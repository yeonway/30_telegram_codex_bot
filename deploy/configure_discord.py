#!/usr/bin/env python3
"""Securely add Discord credentials to the protected service environment file."""

from __future__ import annotations

import getpass
import os
import re
import tempfile
from pathlib import Path


ENV_PATH = Path("/etc/telegram-codex-bot.env")
DISCORD_KEYS = {
    "DISCORD_BOT_TOKEN",
    "DISCORD_ALLOWED_USER_ID",
    "DISCORD_ALLOWED_CHANNEL_ID",
}


def positive_id(prompt: str, required: bool = True) -> str:
    while True:
        value = input(prompt).strip()
        if not value and not required:
            return ""
        if value.isdigit() and int(value) > 0:
            return value
        print("양의 숫자 ID를 입력하세요.")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("sudo로 실행하세요.")
    if not ENV_PATH.is_file():
        raise SystemExit(f"환경 파일이 없습니다: {ENV_PATH}")

    token = getpass.getpass("Discord bot token (숨김): ").strip()
    if len(token) < 30 or re.search(r"\s", token):
        raise SystemExit("Discord bot token 형식이 올바르지 않습니다.")
    user_id = positive_id("허용할 Discord 사용자 ID: ")
    channel_id = positive_id("허용할 서버 채널 ID (DM 전용이면 Enter): ", required=False)

    stat = ENV_PATH.stat()
    existing = ENV_PATH.read_text(encoding="utf-8").splitlines()
    kept = [
        line
        for line in existing
        if line.split("=", 1)[0].strip() not in DISCORD_KEYS
    ]
    kept.extend(
        [
            f"DISCORD_BOT_TOKEN={token}",
            f"DISCORD_ALLOWED_USER_ID={user_id}",
        ]
    )
    if channel_id:
        kept.append(f"DISCORD_ALLOWED_CHANNEL_ID={channel_id}")

    fd, temp_name = tempfile.mkstemp(prefix=".telegram-codex-bot.env.", dir=ENV_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept).rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.chown(temp_name, stat.st_uid, stat.st_gid)
        os.replace(temp_name, ENV_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print("Discord 설정을 안전하게 저장했습니다. 토큰 값은 출력하지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
