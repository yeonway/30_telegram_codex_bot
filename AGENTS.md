# Codex Relay contributor guide

- Purpose: connect a private Telegram or Discord account to the local Codex CLI.
- Preserve unrelated working-tree changes.
- Never commit or print bot tokens, pairing codes, numeric account IDs, `.env` files, state files, Codex authentication files, or secret environment values.
- Keep the core runtime portable across Linux, macOS, and Windows. Platform-specific behavior must be optional and feature-detected.
- Run `python -m unittest discover -s tests -v` after code changes.
- Run `python -m compileall app.py artifact_delivery.py codex_progress.py discord_bridge.py discord_controls.py relay_errors.py setup_relay.py tests` for syntax validation.

## Raspberry Pi profile

The files under `deploy/` are an optional, host-specific profile. On a configured Pi, create a backup before changing the installed runtime and restart only `telegram-codex-bot.service`.

When working through this relay, never restart that service synchronously because it kills the active response. Use `/usr/local/sbin/telegram-codex-deploy` when that controlled helper is installed; it backs up the deployment and schedules a detached delayed restart.
