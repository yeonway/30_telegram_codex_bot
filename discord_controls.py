"""Button, select-menu, and modal controls for the Discord adapter."""

from __future__ import annotations

import asyncio
from typing import Any


PANEL_COLOR = 0x2B6CB0
SAFE_COLOR = 0x2F855A
DANGER_COLOR = 0xC53030
WARNING_COLOR = 0xDD6B20
MAX_OPTIONS = 25


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class DiscordControls:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge
        self.application = bridge.application
        self.discord = bridge._discord

    def _control_view(self, timeout: float | None = None) -> Any:
        view = self.discord.ui.View(timeout=timeout)

        async def interaction_check(interaction: Any) -> bool:
            user_id = getattr(getattr(interaction, "user", None), "id", None)
            if user_id == self.bridge.allowed_user_id:
                return True
            try:
                await interaction.response.send_message(
                    "이 컨트롤은 허용된 사용자만 조작할 수 있습니다.", ephemeral=True
                )
            except Exception:
                pass
            return False

        view.interaction_check = interaction_check
        return view

    async def send_initial_panel(self) -> None:
        if self.bridge.allowed_user_id is None:
            return
        user = self.bridge.client.get_user(self.bridge.allowed_user_id)
        if user is None:
            user = await self.bridge.client.fetch_user(self.bridge.allowed_user_id)
        channel = user.dm_channel or await user.create_dm()
        await self.send_panel(channel)

    async def send_panel(self, channel: Any) -> None:
        embed, view = self.build_main_panel()
        await channel.send(
            embed=embed,
            view=view,
            allowed_mentions=self.discord.AllowedMentions.none(),
        )

    def _snapshot(self) -> dict[str, Any]:
        return self.application.control_snapshot("discord")

    def _status_embed(self, *, settings: bool = False) -> Any:
        snap = self._snapshot()
        state = snap["state"]
        permission = state.get("permission", "safe")
        colors = {
            "safe": SAFE_COLOR,
            "read": PANEL_COLOR,
            "auto": SAFE_COLOR,
            "full": WARNING_COLOR,
            "root": DANGER_COLOR,
            "root-always": DANGER_COLOR,
        }
        title = "⚙️ AI·권한 설정" if settings else "🎛 Codex 리모컨"
        description = (
            "모델·추론 강도·권한을 선택하세요. 위험 권한은 한 번 더 확인합니다."
            if settings
            else "아래 버튼으로 선택하거나, 메시지를 보내 바로 작업하세요."
        )
        embed = self.discord.Embed(
            title=title,
            description=description,
            color=colors.get(permission, PANEL_COLOR),
        )
        embed.add_field(
            name="작업 위치",
            value=f"`{snap['current'] or '없음'}`\n세션: `{snap['session'] or '없음'}`",
            inline=True,
        )
        embed.add_field(
            name="AI 설정",
            value=(
                f"모델: `{state.get('model') or 'default'}`\n"
                f"추론: `{state.get('intelligence') or 'default'}`"
            ),
            inline=True,
        )
        run_text = (
            f"현재 세션 실행 중 · {snap['current_run']['elapsed']}초"
            if snap["current_run"]
            else (f"다른 세션 포함 {len(snap['running'])}개 실행 중" if snap["running"] else "대기")
        )
        permission_label = {
            "read": "읽기 전용",
            "safe": "프로젝트 수정",
            "auto": "자동 검토",
            "full": "전체 접근 ⚠️",
            "root": "root 1회 준비됨 🚨",
            "root-always": "root 계속 🚨",
        }.get(permission, str(permission))
        embed.add_field(
            name="상태",
            value=f"{run_text}\n권한: **{permission_label}**",
            inline=False,
        )
        embed.set_footer(text="패널이 오래되어 동작하지 않으면 !panel으로 새로 여세요.")
        return embed

    def _select(
        self,
        *,
        placeholder: str,
        options: list[Any],
        row: int,
        custom_id: str,
        disabled: bool = False,
    ) -> Any:
        return self.discord.ui.Select(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            row=row,
            custom_id=custom_id,
            disabled=disabled,
        )

    def build_main_panel(self) -> tuple[Any, Any]:
        app = self.application
        snap = self._snapshot()
        current = snap["current"]
        session = snap["session"]
        view = self._control_view(timeout=None)

        projects = app.projects.list_projects()
        project_options = [
            self.discord.SelectOption(
                label=_short(name, 100),
                value=name,
                default=name == current,
                description="현재 프로젝트" if name == current else None,
            )
            for name in projects[:MAX_OPTIONS]
        ]
        if not project_options:
            project_options = [self.discord.SelectOption(label="프로젝트 없음", value="__none__")]
        project_select = self._select(
            placeholder="프로젝트 선택",
            options=project_options,
            row=0,
            custom_id="codex:project",
            disabled=not projects,
        )

        async def project_changed(interaction: Any) -> None:
            await self._apply(interaction, f"/use {project_select.values[0]}", "main")

        project_select.callback = project_changed
        view.add_item(project_select)

        sessions = app.state.list_sessions(current, limit=10, context="discord") if current else {}
        session_options = [
            self.discord.SelectOption(
                label=_short(name, 100),
                value=name,
                default=name == session,
                description="대화 있음" if session_id else "새 대화",
            )
            for name, session_id in sessions.items()
        ]
        if not session_options:
            session_options = [self.discord.SelectOption(label="세션 없음", value="__none__")]
        session_select = self._select(
            placeholder="세션 선택",
            options=session_options,
            row=1,
            custom_id="codex:session",
            disabled=not sessions,
        )

        async def session_changed(interaction: Any) -> None:
            await self._apply(interaction, f"/session {session_select.values[0]}", "main")

        session_select.callback = session_changed
        view.add_item(session_select)

        refresh = self.discord.ui.Button(
            label="새로고침", emoji="🔄", style=self.discord.ButtonStyle.secondary, row=3,
            custom_id="codex:refresh",
        )
        reset = self.discord.ui.Button(
            label="대화 초기화", emoji="🧹", style=self.discord.ButtonStyle.secondary, row=2,
            custom_id="codex:reset", disabled=not current or bool(snap["current_run"]),
        )
        cancel = self.discord.ui.Button(
            label="현재 중지", emoji="⏹️", style=self.discord.ButtonStyle.danger, row=2,
            custom_id="codex:cancel", disabled=not bool(snap["current_run"]),
        )
        cancel_all = self.discord.ui.Button(
            label="모두 중지", emoji="⏹️", style=self.discord.ButtonStyle.danger, row=3,
            custom_id="codex:cancel-all", disabled=not bool(snap["running"]),
        )
        settings = self.discord.ui.Button(
            label="AI·권한 설정", emoji="⚙️", style=self.discord.ButtonStyle.primary, row=2,
            custom_id="codex:settings",
        )
        status = self.discord.ui.Button(
            label="상태", emoji="📊", style=self.discord.ButtonStyle.secondary, row=2,
            custom_id="codex:status",
        )
        sessions_button = self.discord.ui.Button(
            label="세션 관리", emoji="💬", style=self.discord.ButtonStyle.secondary, row=3,
            custom_id="codex:sessions", disabled=not current,
        )
        help_button = self.discord.ui.Button(
            label="도움말", emoji="❓", style=self.discord.ButtonStyle.secondary, row=3,
            custom_id="codex:help",
        )

        async def refresh_clicked(interaction: Any) -> None:
            embed, refreshed = self.build_main_panel()
            await interaction.response.edit_message(embed=embed, view=refreshed)

        async def reset_clicked(interaction: Any) -> None:
            await interaction.response.edit_message(
                embed=self._confirm_embed(
                    "대화 초기화",
                    "현재 세션의 Codex 대화 연결을 초기화합니다. 파일은 삭제하지 않습니다.",
                ),
                view=self._confirmation_view("/new", "대화 초기화", "main"),
            )

        async def cancel_clicked(interaction: Any) -> None:
            await self._apply(interaction, "/cancel", "main")

        async def cancel_all_clicked(interaction: Any) -> None:
            await self._apply(interaction, "/cancel all", "main")

        async def settings_clicked(interaction: Any) -> None:
            embed, settings_view = self.build_settings_panel()
            await interaction.response.edit_message(embed=embed, view=settings_view)

        async def status_clicked(interaction: Any) -> None:
            await self._show_feedback(interaction, "/status")

        async def sessions_clicked(interaction: Any) -> None:
            embed, sessions_view = self.build_sessions_panel()
            await interaction.response.edit_message(embed=embed, view=sessions_view)

        async def help_clicked(interaction: Any) -> None:
            await self._show_feedback(interaction, "/help")

        refresh.callback = refresh_clicked
        reset.callback = reset_clicked
        cancel.callback = cancel_clicked
        cancel_all.callback = cancel_all_clicked
        settings.callback = settings_clicked
        status.callback = status_clicked
        sessions_button.callback = sessions_clicked
        help_button.callback = help_clicked
        for item in (refresh, reset, cancel, cancel_all, settings):
            view.add_item(item)
        view.add_item(status)
        view.add_item(sessions_button)
        view.add_item(help_button)
        return self._status_embed(), view

    def build_sessions_panel(self) -> tuple[Any, Any]:
        """Build the Discord equivalent of Telegram's session submenu."""
        snap = self._snapshot()
        current = snap["current"]
        selected = snap["session"]
        view = self._control_view(timeout=None)
        sessions = self.application.state.list_sessions(
            current, limit=10, context="discord"
        ) if current else {}
        options = [
            self.discord.SelectOption(
                label=_short(name, 100), value=name, default=name == selected,
                description="대화 있음" if session_id else "새 대화",
            )
            for name, session_id in sessions.items()
        ] or [self.discord.SelectOption(label="세션 없음", value="__none__")]
        session_select = self._select(
            placeholder="세션 선택", options=options, row=0,
            custom_id="codex:session:manage", disabled=not sessions,
        )

        async def session_changed(interaction: Any) -> None:
            await self._apply(interaction, f"/session {session_select.values[0]}", "sessions")

        session_select.callback = session_changed
        view.add_item(session_select)
        new_session = self.discord.ui.Button(
            label="새 세션", emoji="➕", style=self.discord.ButtonStyle.secondary, row=1,
            custom_id="codex:new-session", disabled=not current,
        )
        rename_session = self.discord.ui.Button(
            label="이름 변경", emoji="✏️", style=self.discord.ButtonStyle.secondary, row=1,
            custom_id="codex:rename-session", disabled=not current or bool(snap["current_run"]),
        )
        delete_session = self.discord.ui.Button(
            label="세션 삭제", emoji="🗑️", style=self.discord.ButtonStyle.danger, row=1,
            custom_id="codex:delete-session", disabled=not current or bool(snap["current_run"]),
        )
        back = self.discord.ui.Button(
            label="메인 메뉴", emoji="⬅️", style=self.discord.ButtonStyle.primary, row=2,
            custom_id="codex:back-main",
        )

        async def new_session_clicked(interaction: Any) -> None:
            await self._show_new_session_modal(interaction, "sessions")

        async def rename_session_clicked(interaction: Any) -> None:
            await self._show_rename_session_modal(interaction, "sessions")

        async def delete_session_clicked(interaction: Any) -> None:
            current_name = self._snapshot()["session"]
            if not current_name:
                await interaction.response.send_message("삭제할 세션이 없습니다.", ephemeral=True)
                return
            await interaction.response.edit_message(
                embed=self._confirm_embed(
                    "세션 삭제",
                    f"`{current_name}` 세션의 저장된 Codex 대화 연결을 삭제합니다. 프로젝트 파일은 삭제하지 않습니다.",
                    dangerous=True,
                ),
                view=self._confirmation_view(
                    f"/session delete {current_name} confirm", "세션 삭제", "sessions", dangerous=True,
                ),
            )

        async def back_clicked(interaction: Any) -> None:
            embed, main = self.build_main_panel()
            await interaction.response.edit_message(embed=embed, view=main)

        new_session.callback = new_session_clicked
        rename_session.callback = rename_session_clicked
        delete_session.callback = delete_session_clicked
        back.callback = back_clicked
        for item in (new_session, rename_session, delete_session, back):
            view.add_item(item)
        return self._sessions_embed(current, selected), view

    def _sessions_embed(self, current: str | None, session: str | None) -> Any:
        embed = self.discord.Embed(
            title="💬 세션 선택",
            description=f"최근 세션을 선택하세요.\n프로젝트: `{current or '없음'}`",
            color=PANEL_COLOR,
        )
        embed.add_field(name="현재 세션", value=f"`{session or '없음'}`", inline=False)
        embed.set_footer(text="메인 메뉴로 돌아가려면 아래 버튼을 누르세요.")
        return embed

    def build_settings_panel(self) -> tuple[Any, Any]:
        app = self.application
        snap = self._snapshot()
        state = snap["state"]
        current_model = state.get("model")
        current_intelligence = state.get("intelligence")
        disabled = False
        view = self._control_view(timeout=None)

        models = app._available_models()
        selected_models = models[: MAX_OPTIONS - 1]
        if isinstance(current_model, str) and current_model not in selected_models:
            selected_models = [current_model, *selected_models[: MAX_OPTIONS - 2]]
        model_options = [
            self.discord.SelectOption(
                label="default · 자동 선택",
                value="default",
                default=current_model is None,
            )
        ] + [
            self.discord.SelectOption(
                label=_short(name, 100), value=name, default=name == current_model
            )
            for name in selected_models
        ]
        model_select = self._select(
            placeholder="모델 선택", options=model_options, row=0,
            custom_id="codex:model", disabled=disabled,
        )

        async def model_changed(interaction: Any) -> None:
            await self._apply(interaction, f"/model {model_select.values[0]}", "settings")

        model_select.callback = model_changed
        view.add_item(model_select)

        levels = app._available_intelligence_levels(
            current_model if isinstance(current_model, str) else None
        ) or list(app.reasoning_levels)
        intelligence_options = [
            self.discord.SelectOption(
                label="default · 자동 선택",
                value="default",
                default=current_intelligence is None,
            )
        ] + [
            self.discord.SelectOption(
                label=level, value=level, default=level == current_intelligence
            )
            for level in levels[: MAX_OPTIONS - 1]
        ]
        intelligence_select = self._select(
            placeholder="추론 강도 선택", options=intelligence_options, row=1,
            custom_id="codex:intelligence", disabled=disabled,
        )

        async def intelligence_changed(interaction: Any) -> None:
            await self._apply(
                interaction, f"/intelligence {intelligence_select.values[0]}", "settings"
            )

        intelligence_select.callback = intelligence_changed
        view.add_item(intelligence_select)

        permission = state.get("permission", "safe")
        for label, value, emoji in (
            ("프로젝트 수정", "safe", "🛠️"),
            ("읽기 전용", "read", "👁️"),
            ("자동 검토", "auto", "🛡️"),
        ):
            button = self.discord.ui.Button(
                label=("✓ " if permission == value else "") + label,
                emoji=emoji,
                style=(
                    self.discord.ButtonStyle.success
                    if permission == value
                    else self.discord.ButtonStyle.secondary
                ),
                row=2,
                custom_id=f"codex:permission:{value}",
                disabled=disabled,
            )

            async def permission_clicked(interaction: Any, selected: str = value) -> None:
                await self._apply(interaction, f"/permission {selected}", "settings")

            button.callback = permission_clicked
            view.add_item(button)

        full = self.discord.ui.Button(
            label=("✓ " if permission == "full" else "") + "전체 접근 1회",
            emoji="⚠️", style=self.discord.ButtonStyle.danger, row=3,
            custom_id="codex:permission:full", disabled=disabled,
        )
        root = self.discord.ui.Button(
            label=("✓ " if permission == "root" else "") + "root 1회",
            emoji="🚨", style=self.discord.ButtonStyle.danger, row=3,
            custom_id="codex:permission:root", disabled=disabled,
        )
        root_always = self.discord.ui.Button(
            label=("✓ " if permission == "root-always" else "") + "root 계속",
            emoji="🚨", style=self.discord.ButtonStyle.danger, row=3,
            custom_id="codex:permission:root-always", disabled=disabled,
        )
        back = self.discord.ui.Button(
            label="컨트롤로 돌아가기", emoji="↩️", style=self.discord.ButtonStyle.primary, row=4,
            custom_id="codex:back",
        )

        async def full_clicked(interaction: Any) -> None:
            await interaction.response.edit_message(
                embed=self._confirm_embed(
                    "전체 접근 권한",
                    "Codex가 사용자 계정 범위에서 샌드박스와 승인을 우회합니다. 다음 작업 시작 즉시 프로젝트 수정 권한으로 복귀합니다.",
                    dangerous=True,
                ),
                view=self._confirmation_view("/permission full confirm", "전체 접근 1회 준비", "settings", dangerous=True),
            )

        async def root_clicked(interaction: Any) -> None:
            await interaction.response.edit_message(
                embed=self._confirm_embed(
                    "root 1회 권한",
                    "다음 작업 한 번만 Pi 전체를 root로 변경할 수 있습니다. 작업 시작과 동시에 safe로 복귀합니다.",
                    dangerous=True,
                ),
                view=self._confirmation_view(
                    "/permission root confirm", "root 1회 준비", "settings", dangerous=True
                ),
            )

        async def root_always_clicked(interaction: Any) -> None:
            await interaction.response.edit_message(
                embed=self._confirm_embed(
                    "root 계속 권한",
                    "이후 모든 작업을 Pi 전체 접근이 가능한 root로 실행합니다. safe·read·auto 권한을 선택할 때까지, 서비스가 재시작되어도 유지됩니다.",
                    dangerous=True,
                ),
                view=self._confirmation_view(
                    "/permission root always confirm", "root 계속 적용", "settings", dangerous=True
                ),
            )

        async def back_clicked(interaction: Any) -> None:
            embed, main = self.build_main_panel()
            await interaction.response.edit_message(embed=embed, view=main)

        full.callback = full_clicked
        root.callback = root_clicked
        root_always.callback = root_always_clicked
        back.callback = back_clicked
        for item in (full, root, root_always, back):
            view.add_item(item)
        return self._status_embed(settings=True), view

    def _confirm_embed(self, title: str, description: str, dangerous: bool = False) -> Any:
        embed = self.discord.Embed(
            title=title,
            description=description,
            color=DANGER_COLOR if dangerous else WARNING_COLOR,
        )
        embed.add_field(name="확인 필요", value="계속하거나 취소하세요.", inline=False)
        return embed

    def _confirmation_view(
        self,
        command: str,
        confirm_label: str,
        return_panel: str,
        dangerous: bool = False,
    ) -> Any:
        view = self._control_view(timeout=300)
        confirm = self.discord.ui.Button(
            label=confirm_label,
            style=self.discord.ButtonStyle.danger if dangerous else self.discord.ButtonStyle.primary,
            custom_id=f"codex:confirm:{command}",
        )
        cancel = self.discord.ui.Button(
            label="취소", style=self.discord.ButtonStyle.secondary,
            custom_id=f"codex:confirm:cancel:{return_panel}",
        )

        async def confirmed(interaction: Any) -> None:
            await self._apply(interaction, command, return_panel)

        async def cancelled(interaction: Any) -> None:
            embed, restored = self._build_panel(return_panel)
            await interaction.response.edit_message(embed=embed, view=restored)

        confirm.callback = confirmed
        cancel.callback = cancelled
        view.add_item(confirm)
        view.add_item(cancel)
        return view

    def _build_panel(self, target: str) -> tuple[Any, Any]:
        if target == "settings":
            return self.build_settings_panel()
        if target == "sessions":
            return self.build_sessions_panel()
        return self.build_main_panel()

    async def _show_new_session_modal(self, interaction: Any, target: str = "main") -> None:
        discord = self.discord
        modal = discord.ui.Modal(title="새 Codex 세션", timeout=300)
        name_input = discord.ui.TextInput(
            label="세션 이름",
            placeholder="예: bugfix 또는 deploy",
            min_length=1,
            max_length=40,
            required=True,
            style=discord.TextStyle.short,
        )
        modal.add_item(name_input)
        panel_message = interaction.message

        async def submitted(modal_interaction: Any) -> None:
            feedback = await asyncio.to_thread(
                self._capture_command,
                int(modal_interaction.channel_id),
                f"/session new {str(name_input.value).strip()}",
            )
            embed, refreshed = self._build_panel(target)
            await panel_message.edit(embed=embed, view=refreshed)
            await modal_interaction.response.send_message(feedback, ephemeral=True)

        modal.on_submit = submitted
        await interaction.response.send_modal(modal)

    async def _show_rename_session_modal(self, interaction: Any, target: str = "main") -> None:
        current_name = self._snapshot()["session"]
        if not current_name:
            await interaction.response.send_message("이름을 변경할 세션이 없습니다.", ephemeral=True)
            return
        discord = self.discord
        modal = discord.ui.Modal(title="세션 이름 변경", timeout=300)
        name_input = discord.ui.TextInput(
            label="새 세션 이름",
            default=current_name,
            min_length=1,
            max_length=40,
            required=True,
            style=discord.TextStyle.short,
        )
        modal.add_item(name_input)
        panel_message = interaction.message

        async def submitted(modal_interaction: Any) -> None:
            feedback = await asyncio.to_thread(
                self._capture_command,
                int(modal_interaction.channel_id),
                f"/session rename {str(name_input.value).strip()}",
            )
            embed, refreshed = self._build_panel(target)
            await panel_message.edit(embed=embed, view=refreshed)
            await modal_interaction.response.send_message(feedback, ephemeral=True)

        modal.on_submit = submitted
        await interaction.response.send_modal(modal)

    def _capture_command(self, channel_id: int, command: str) -> str:
        relay = self.application.client
        with relay.capture_messages() as messages:
            self.application._handle_authorized(-channel_id, command)
        return _short("\n\n".join(messages) or "완료했습니다.", 1900)

    async def _apply(self, interaction: Any, command: str, target: str) -> None:
        await interaction.response.defer(ephemeral=True)
        feedback = await asyncio.to_thread(
            self._capture_command, int(interaction.channel_id), command
        )
        embed, view = self._build_panel(target)
        await interaction.message.edit(embed=embed, view=view)
        await interaction.followup.send(feedback, ephemeral=True)

    async def _show_feedback(self, interaction: Any, command: str) -> None:
        await interaction.response.defer(ephemeral=True)
        feedback = await asyncio.to_thread(
            self._capture_command, int(interaction.channel_id), command
        )
        await interaction.followup.send(feedback, ephemeral=True)
