#!/usr/bin/env python3
"""Verify the production project catalog without exposing environment secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import Config, ProjectCatalog


def main() -> int:
    config = Config.from_env()
    catalog = ProjectCatalog(config.project_root, config.extra_projects)
    projects = catalog.list_projects()
    zeta_path = catalog.resolve("zeta-chat-ui")
    result = {
        "ok": "zeta-chat-ui" in projects,
        "count": len(projects),
        "projects": projects,
        "zeta_path": str(zeta_path),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
