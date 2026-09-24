"""Validated artifact handoff from Codex runs to the public Drive site."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_ARTIFACTS = 5
MAX_MANIFEST_BYTES = 64 * 1024
PUBLISHER = "/usr/local/sbin/telegram-codex-publish-artifact"


class ArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactRequest:
    path: Path
    title: str
    description: str
    publish_as: str = "file"
    app_name: str | None = None
    version: str | None = None


def load_artifact_requests(outbox: Path) -> list[ArtifactRequest]:
    """Load a small, path-confined manifest produced by a Codex run."""
    manifest = outbox / "artifacts.json"
    if not manifest.is_file():
        return []
    if manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise ArtifactError("산출물 목록이 너무 큽니다.")
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("산출물 목록을 읽지 못했습니다.") from exc
    if not isinstance(raw, list) or len(raw) > MAX_ARTIFACTS:
        raise ArtifactError(f"산출물은 최대 {MAX_ARTIFACTS}개까지 게시할 수 있습니다.")

    root = outbox.resolve()
    requests: list[ArtifactRequest] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ArtifactError("산출물 항목 형식이 올바르지 않습니다.")
        relative = item.get("path")
        title = _text(item.get("title"), 120)
        description = _text(item.get("description"), 500, required=False)
        publish_as = _text(item.get("publish_as") or "file", 16)
        if not isinstance(relative, str) or not relative.strip() or not title:
            raise ArtifactError("산출물 path와 title이 필요합니다.")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ArtifactError("산출물 경로가 보관함을 벗어났습니다.") from exc
        if candidate == manifest.resolve() or not candidate.is_file() or candidate.is_symlink():
            raise ArtifactError(f"게시할 파일을 찾지 못했습니다: {relative}")
        if publish_as not in {"file", "release"}:
            raise ArtifactError("publish_as는 file 또는 release여야 합니다.")
        app_name = _text(item.get("app_name"), 120, required=False) or None
        version = _text(item.get("version"), 80, required=False) or None
        if publish_as == "release" and (not app_name or not version):
            raise ArtifactError("릴리스 게시에는 app_name과 version이 필요합니다.")
        requests.append(
            ArtifactRequest(
                path=candidate,
                title=title,
                description=description,
                publish_as=publish_as,
                app_name=app_name,
                version=version,
            )
        )
    return requests


def publish_artifacts(
    requests: list[ArtifactRequest], publisher: str = PUBLISHER
) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    for request in requests:
        command = [
            "/usr/bin/sudo",
            "-n",
            publisher,
            "--source",
            str(request.path),
            "--title",
            request.title,
            "--description",
            request.description,
            "--publish-as",
            request.publish_as,
        ]
        if request.app_name:
            command.extend(["--app-name", request.app_name])
        if request.version:
            command.extend(["--version", request.version])
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "게시 실패").strip()[-800:]
            raise ArtifactError(detail)
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ArtifactError("게시 결과 형식이 올바르지 않습니다.") from exc
        if not isinstance(result, dict) or not result.get("url") or not result.get("sha256"):
            raise ArtifactError("게시 결과에 URL 또는 SHA-256이 없습니다.")
        published.append(result)
    return published


def render_artifact_cards(items: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in items:
        title = str(item.get("title") or "다운로드")[:120]
        kind = str(item.get("type") or "FILE").upper()[:12]
        size = _format_size(int(item.get("size") or 0))
        digest = str(item.get("sha256") or "")[:12]
        url = str(item.get("url") or "")
        cards.append(
            f"📦 {title}\n"
            f"{kind} · {size}\n"
            f"SHA-256: {digest}…\n"
            f"⬇️ {url}"
        )
    return "\n\n".join(cards)


def _text(value: Any, limit: int, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _format_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"
