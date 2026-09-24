#!/usr/bin/env python3
"""Verify the registered Telegram menu command and send the live control panel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def main() -> int:
    config = app.Config.from_env()
    bot = app.BotApplication(config)
    state = bot.state.snapshot()
    chat_id = state.get("allowed_chat_id")
    if not isinstance(chat_id, int):
        raise RuntimeError("Telegram is not paired")

    commands = bot.client.call("getMyCommands")
    menu_registered = any(
        isinstance(item, dict) and item.get("command") == "menu"
        for item in commands or []
    )
    if not menu_registered:
        raise RuntimeError("Telegram /menu command is not registered")

    bot._send_telegram_menu(chat_id)
    print(json.dumps({"ok": True, "menu_registered": True, "menu_sent": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
