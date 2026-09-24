"""Platform-independent rendering of public Codex CLI progress events."""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable


MAX_PROGRESS_TEXT = 1600
MAX_STEPS = 10


class CodexProgress:
    """Accumulate safe, public JSONL events into one editable status message."""

    def __init__(
        self,
        *,
        started_at: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self.started_at = clock() if started_at is None else started_at
        self._steps: list[str] = []
        self._lock = threading.RLock()

    def add_step(self, text: str) -> bool:
        step = _clean_summary(text)
        if not step:
            return False
        with self._lock:
            if self._steps and self._steps[-1] == step:
                return False
            self._steps.append(step)
            if len(self._steps) > MAX_STEPS:
                self._steps = self._steps[-MAX_STEPS:]
        return True

    def apply_event(self, event: dict[str, Any]) -> bool:
        """Consume only Codex's public summaries and coarse action metadata.

        Raw reasoning, command output, stderr, and command arguments are
        deliberately ignored so progress messages cannot leak secrets or hidden
        chain-of-thought.
        """
        event_type = str(event.get("type") or "").replace(".", "_")
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        item_type = str(item.get("type") or "")

        if event_type == "agent_reasoning":
            return self.add_step(_public_summary(event))
        if item_type == "reasoning" and event_type in {
            "item_started",
            "item_updated",
            "item_completed",
        }:
            return self.add_step(_public_summary(item))
        if event_type == "plan_update":
            plan = event.get("plan")
            if isinstance(plan, list):
                changed = False
                for entry in plan:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("status") in {"in_progress", "completed"}:
                        changed = self.add_step(str(entry.get("step") or "")) or changed
                return changed
        if event_type in {"patch_apply_begin", "patch_apply_updated", "patch_apply_end"}:
            return self.add_step("파일 수정")
        if item_type == "file_change":
            return self.add_step("파일 수정")
        if event_type in {"web_search_begin", "web_search_end"} or item_type == "web_search":
            return self.add_step("자료 검색")
        if event_type in {"mcp_tool_call_begin", "mcp_tool_call_end"} or item_type == "mcp_tool_call":
            return self.add_step("도구 실행")
        if event_type in {"exec_command_begin", "exec_command_end"} or item_type == "command_execution":
            command = event.get("command") or item.get("command")
            return self.add_step(_command_label(command))
        if event_type in {"task_started", "turn_started"}:
            return self.add_step("Codex 작업 시작")
        return False

    def render(self, outcome: str = "running") -> str:
        with self._lock:
            steps = list(self._steps)
        elapsed = max(0.0, self._clock() - self.started_at)
        if outcome == "success":
            heading = "✅ 작업 완료"
            timer = f"⏱ 총 소요 시간: {elapsed:.1f}초"
        elif outcome == "cancelled":
            heading = "⏹️ 작업 중지"
            timer = f"⏱ 총 소요 시간: {elapsed:.1f}초"
        elif outcome == "failed":
            heading = "❌ 작업 실패"
            timer = f"⏱ 총 소요 시간: {elapsed:.1f}초"
        else:
            heading = "🧠 작업 중..."
            timer = f"⏱ 경과 시간: {int(elapsed)}초"
        body = "\n→ ".join(steps or ["Codex 실행 준비"])
        result = f"{heading}\n\n{body}\n\n{timer}"
        return result[:MAX_PROGRESS_TEXT]


def _public_summary(value: dict[str, Any]) -> str:
    # These fields are explicitly emitted as public summary text by Codex CLI.
    # Never fall back to raw_content or encrypted_content.
    for key in ("summary_text", "summary", "text"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            return candidate
        if isinstance(candidate, list):
            parts: list[str] = []
            for entry in candidate:
                if isinstance(entry, str):
                    parts.append(entry)
                elif isinstance(entry, dict):
                    text = entry.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return " ".join(parts)
    return ""


def _clean_summary(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    compact = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: Bearer [REDACTED]", compact)
    compact = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot[REDACTED]", compact)
    return compact[:180]


def _command_label(command: Any) -> str:
    if isinstance(command, list):
        command = " ".join(str(part) for part in command[:3])
    if not isinstance(command, str):
        return "명령 실행"
    lowered = command.lower()
    if re.search(r"(^|\s)(rg|find|ls|tree)(\s|$)", lowered):
        return "파일 구조 확인"
    if re.search(r"(^|\s)(sed|head|tail|cat)(\s|$)", lowered):
        return "코드 분석"
    if "apply_patch" in lowered or "git apply" in lowered:
        return "파일 수정"
    if "unittest" in lowered or "pytest" in lowered:
        return "테스트 실행"
    if "compileall" in lowered or "py_compile" in lowered:
        return "문법 검사"
    if "git status" in lowered or "git diff" in lowered:
        return "변경사항 확인"
    return "명령 실행"
