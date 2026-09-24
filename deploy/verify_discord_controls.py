#!/usr/bin/env python3
"""Validate Discord control component structure without exposing credentials."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
from discord_bridge import DiscordBridge, RelayClient


def validate_view(view, expected_rows: dict[int, int]) -> list[str]:
    rows: dict[int, int] = {}
    custom_ids: list[str] = []
    for child in view.children:
        row = int(child.row) if child.row is not None else 0
        rows[row] = rows.get(row, 0) + 1
        custom_id = getattr(child, "custom_id", None)
        if custom_id:
            custom_ids.append(custom_id)
        options = getattr(child, "options", None)
        if options is not None:
            assert 1 <= len(options) <= 25
    assert rows == expected_rows, (rows, expected_rows)
    assert len(custom_ids) == len(set(custom_ids))
    assert max(rows, default=0) <= 4
    assert all(count <= 5 for count in rows.values())
    return custom_ids


class FakeResponse:
    def __init__(self) -> None:
        self.deferred = False
        self.edited = False
        self.view = None
        self.modal = None
        self.sent = False

    async def defer(self, **_kwargs) -> None:
        self.deferred = True

    async def edit_message(self, **kwargs) -> None:
        self.edited = True
        self.view = kwargs.get("view")

    async def send_modal(self, modal) -> None:
        self.modal = modal

    async def send_message(self, *_args, **_kwargs) -> None:
        self.sent = True


class FakeMessage:
    def __init__(self) -> None:
        self.edited = False

    async def edit(self, **_kwargs) -> None:
        self.edited = True


class FakeFollowup:
    def __init__(self) -> None:
        self.sent = False

    async def send(self, *_args, **_kwargs) -> None:
        self.sent = True


class FakeInteraction:
    def __init__(self) -> None:
        self.channel_id = 123
        self.response = FakeResponse()
        self.message = FakeMessage()
        self.followup = FakeFollowup()


async def exercise_callbacks(bridge: DiscordBridge) -> None:
    _embed, main_view = bridge.controls.build_main_panel()
    refresh = next(item for item in main_view.children if item.custom_id == "codex:refresh")
    refresh_interaction = FakeInteraction()
    await refresh.callback(refresh_interaction)
    assert refresh_interaction.response.edited

    status = next(item for item in main_view.children if item.custom_id == "codex:status")
    status_interaction = FakeInteraction()
    await status.callback(status_interaction)
    assert status_interaction.response.deferred
    assert status_interaction.followup.sent

    help_button = next(item for item in main_view.children if item.custom_id == "codex:help")
    help_interaction = FakeInteraction()
    await help_button.callback(help_interaction)
    assert help_interaction.response.deferred
    assert help_interaction.followup.sent

    sessions_button = next(
        item for item in main_view.children if item.custom_id == "codex:sessions"
    )
    modal_interaction = FakeInteraction()
    await sessions_button.callback(modal_interaction)
    assert modal_interaction.response.edited
    sessions_view = modal_interaction.response.view
    new_session = next(
        item for item in sessions_view.children if item.custom_id == "codex:new-session"
    )
    modal_interaction = FakeInteraction()
    await new_session.callback(modal_interaction)
    assert modal_interaction.response.modal is not None
    name_input = modal_interaction.response.modal.children[0]
    name_input._value = "ui-verify"
    submit_interaction = FakeInteraction()
    await modal_interaction.response.modal.on_submit(submit_interaction)
    assert submit_interaction.response.sent
    current = bridge.application.state.snapshot("discord")["current_project"]
    assert bridge.application.state.current_session(current, context="discord") == "ui-verify"

    bridge.application.state.set_session(
        current, "ui-verify", "preserved-session-id", context="discord"
    )
    _embed, sessions_view = bridge.controls.build_sessions_panel()
    rename_session = next(
        item for item in sessions_view.children if item.custom_id == "codex:rename-session"
    )
    rename_interaction = FakeInteraction()
    await rename_session.callback(rename_interaction)
    assert rename_interaction.response.modal is not None
    rename_input = rename_interaction.response.modal.children[0]
    rename_input._value = "ui-renamed"
    rename_submit = FakeInteraction()
    await rename_interaction.response.modal.on_submit(rename_submit)
    assert rename_submit.response.sent
    assert bridge.application.state.current_session(current, context="discord") == "ui-renamed"
    assert (
        bridge.application.state.list_sessions(current, context="discord")["ui-renamed"]
        == "preserved-session-id"
    )

    _embed, sessions_view = bridge.controls.build_sessions_panel()
    delete_session = next(
        item for item in sessions_view.children if item.custom_id == "codex:delete-session"
    )
    delete_interaction = FakeInteraction()
    await delete_session.callback(delete_interaction)
    assert delete_interaction.response.edited
    delete_confirm = next(
        item
        for item in delete_interaction.response.view.children
        if item.custom_id.startswith("codex:confirm:/session delete")
    )
    delete_confirm_interaction = FakeInteraction()
    await delete_confirm.callback(delete_confirm_interaction)
    assert delete_confirm_interaction.response.deferred
    assert delete_confirm_interaction.message.edited
    assert delete_confirm_interaction.followup.sent
    assert "ui-renamed" not in bridge.application.state.list_sessions(current, context="discord")
    assert bridge.application.state.current_session(current, context="discord") == "main"

    _embed, settings_view = bridge.controls.build_settings_panel()
    full = next(
        item for item in settings_view.children if item.custom_id == "codex:permission:full"
    )
    full_interaction = FakeInteraction()
    await full.callback(full_interaction)
    assert full_interaction.response.edited
    confirm = next(
        item
        for item in full_interaction.response.view.children
        if item.custom_id.startswith("codex:confirm:/permission full")
    )
    confirm_interaction = FakeInteraction()
    await confirm.callback(confirm_interaction)
    assert confirm_interaction.response.deferred
    assert confirm_interaction.message.edited
    assert confirm_interaction.followup.sent
    assert bridge.application.state.snapshot("discord")["permission"] == "full"

    _embed, settings_view = bridge.controls.build_settings_panel()
    safe = next(
        item for item in settings_view.children if item.custom_id == "codex:permission:safe"
    )
    safe_interaction = FakeInteraction()
    await safe.callback(safe_interaction)
    assert bridge.application.state.snapshot("discord")["permission"] == "safe"


def main() -> int:
    config = app.Config.from_env()
    assert config.discord_bot_token
    assert config.discord_allowed_user_id
    with tempfile.TemporaryDirectory(prefix="discord-controls-") as temp_dir:
        application = app.BotApplication(config)
        application.state = app.StateStore(Path(temp_dir) / "state.json")
        bridge = DiscordBridge(
            application,
            config.discord_bot_token,
            config.discord_allowed_user_id,
            config.discord_allowed_channel_id,
        )
        application.client = RelayClient(application.client, bridge)

        main_embed, main_view = bridge.controls.build_main_panel()
        settings_embed, settings_view = bridge.controls.build_settings_panel()
        full_view = bridge.controls._confirmation_view(
            "/permission full confirm", "전체 접근 1회 준비", "settings", dangerous=True
        )
        root_view = bridge.controls._confirmation_view(
            "/permission root confirm", "root 1회 준비", "settings", dangerous=True
        )
        root_always_view = bridge.controls._confirmation_view(
            "/permission root always confirm", "root 계속 적용", "settings", dangerous=True
        )

        main_ids = validate_view(main_view, {0: 1, 1: 1, 2: 4, 3: 4})
        settings_ids = validate_view(settings_view, {0: 1, 1: 1, 2: 3, 3: 3, 4: 1})
        assert main_view.timeout is None
        assert settings_view.timeout is None
        validate_view(full_view, {0: 2})
        validate_view(root_view, {0: 2})
        validate_view(root_always_view, {0: 2})
        assert main_embed.title == "🎛 Codex 리모컨"
        assert settings_embed.title == "⚙️ AI·권한 설정"
        assert "codex:permission:full" in settings_ids
        assert "codex:permission:root" in settings_ids
        assert "codex:permission:root-always" in settings_ids
        assert "codex:sessions" in main_ids
        assert "codex:status" in main_ids
        assert "codex:help" in main_ids
        assert "codex:cancel-all" in main_ids
        asyncio.run(exercise_callbacks(bridge))
    print(
        json.dumps(
            {
                "ok": True,
                "main_components": len(main_view.children),
                "settings_components": len(settings_view.children),
                "danger_confirmations": 3,
                "callbacks_ok": True,
                "modal_ok": True,
                "session_management_ok": True,
                "persistent_panels": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
