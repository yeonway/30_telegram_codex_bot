# Configuration reference

Use `codex-relay-setup` for normal installation. It writes the sensitive values to a local `.env` file with restrictive permissions.

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | One platform token | Token issued by BotFather |
| `DISCORD_BOT_TOKEN` | One platform token | Token issued by the Discord Developer Portal |
| `BOT_PAIR_CODE_SHA256` | When pairing | SHA-256 of the one-time pairing code |
| `DISCORD_ALLOWED_USER_ID` | No | Skip Discord pairing and pre-authorize one user |
| `DISCORD_ALLOWED_CHANNEL_ID` | No | Additionally allow one server channel |
| `CODEX_PROJECT_ROOT` | Yes | Parent directory containing selectable Git projects |
| `CODEX_EXTRA_PROJECTS` | No | Comma-separated names of explicit non-Git projects below the root |
| `BOT_STATE_FILE` | No | Private JSON state path; defaults to the OS user state directory |
| `CODEX_BINARY` | No | Codex executable name or absolute path; defaults to `codex` on `PATH` |
| `CODEX_HOME` | No | Codex configuration directory; defaults to `~/.codex` |
| `CODEX_TIMEOUT_SECONDS` | No | Per-turn timeout from 60 to 14,400 seconds |
| `CODEX_MAX_CONCURRENT_SESSIONS` | No | Parallel session limit from 1 to 10 |
| `TELEGRAM_POLL_TIMEOUT_SECONDS` | No | Telegram long-poll timeout from 5 to 50 seconds |
| `CODEX_ARTIFACT_ROOT` | No | Private temporary artifact directory |
| `CODEX_ARTIFACT_PUBLISHER` | No | Optional Pi-specific artifact publisher executable |
| `LOG_LEVEL` | No | Python log level, normally `INFO` |

The legacy `TELEGRAM_PAIR_CODE_SHA256` name remains accepted for existing installations. New installations should use `BOT_PAIR_CODE_SHA256` because the same pairing code can authorize either platform.

Do not place OpenAI credentials, Codex authentication files, bot tokens, or the plain pairing code in Git. Codex Relay deliberately reuses `codex login` from the local user account.
