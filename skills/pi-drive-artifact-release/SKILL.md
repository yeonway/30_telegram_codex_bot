---
name: pi-drive-artifact-release
description: Publish APK, EXE, or other approved Codex outputs from the Raspberry Pi to drive.dcout.cloud with a consistent Discord and Telegram download card. Use only when the user requests an externally downloadable artifact or project rules require release publication.
---

# Raspberry Pi Drive Artifact Release

When `CODEX_ARTIFACT_DIR` is available, copy only final deliverables into that directory and create `artifacts.json`. The relay publishes after the Codex turn finishes; do not call the public upload API directly.

Use this schema:

```json
[
  {
    "path": "app-release.apk",
    "title": "JARVIS 1.2.6",
    "description": "External test build",
    "publish_as": "release",
    "app_name": "JARVIS",
    "version": "1.2.6"
  }
]
```

For non-release files use `publish_as: "file"` and omit `app_name` and `version`. Paths must be relative to the artifact directory. Maximum five files are accepted. Do not place source trees, credentials, environment files, signing keys, databases, HTML, JavaScript, SVG, or unrequested logs in the outbox.

The audited publisher creates a backup under `/srv/deploy-backups/telegram-codex-artifacts`, locks the Drive inventory, writes the file and JSON manifest atomically, and re-downloads the public URL to prove size and SHA-256. If publication fails, report it as unverified; do not invent a URL or manually edit `apps.json`/`files.json` to conceal the failure.

Use `release` only for APK or EXE outputs with confirmed name, version, and meaningful description. Existing files and version entries are retained; a matching app name and version updates only its manifest entry and uses a new versioned file.

## Completion

Complete only when the inventory remains valid, the public HTTPS URL returns the exact file size and SHA-256, and the final relay response includes the verified download card. On any mismatch, restore the inventory backup and report publication as failed.