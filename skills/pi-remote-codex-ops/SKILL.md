---
name: pi-remote-codex-ops
description: Operate the Raspberry Pi Codex relay safely from Discord or Telegram, including project/session selection, queued follow-ups, token-usage status, deployment, and service verification. Use for changes to or operation of telegram-codex-bot.service; not for unrelated Pi services.
---

# Raspberry Pi Remote Codex Operations

The source is `/home/user/Raspberry_Pi/30_telegram_codex_bot`, runtime is `/srv/telegram-codex-bot`, and service is `telegram-codex-bot.service`. Preserve the single-user Discord/Telegram authorization boundary and never reveal bot tokens, pairing material, Codex auth files, or secret environment values.

Operational invariants:

- Back up the current runtime and audited system helpers before deployment.
- When deploying the relay from inside itself, use `sudo -n /usr/local/sbin/telegram-codex-deploy`. Never synchronously restart the service from the active relay turn.
- Verify Python and shell syntax, the full unit test suite, sudoers, the systemd unit, source/runtime hashes, service `active` state, `NRestarts`, recent error logs, and both configured platform connections.
- Use `/steer <text>` or send another plain message during a run to queue a follow-up. This CLI relay cannot inject into an active `codex exec`; it starts the prompt immediately after the current turn. Do not describe that queue as true mid-turn steering. Safe/read/auto resumes the saved Codex session; full and root modes remain ephemeral and keep only the project/session slot.
- `/usage` and `/status` show the last JSONL turn token counts. The Pi CLI does not expose remaining account-window percentages; state that limitation instead of estimating.
- Use `$pi-android-apk-build` for APK builds and `$pi-drive-artifact-release` for external downloads.

Keep Discord and Telegram user-facing behavior aligned: one editable progress message, a separate final response, and the same artifact card containing title, type, size, short SHA-256, and HTTPS download URL.

## Completion

Complete only after the requested source and runtime files match, the relevant tests pass, the delayed restart finishes, the service is active without a new restart loop or error log, and each platform that is configured reconnects. Name any platform or live user interaction that could not be verified.