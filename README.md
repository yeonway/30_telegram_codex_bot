# Codex Relay

Run the local Codex CLI from a private Telegram or Discord conversation. Codex Relay keeps the code, Git repositories, and Codex authentication on your own device; Telegram and Discord are only the remote control channel.

It supports Linux, macOS, Windows, Raspberry Pi, Telegram-only, Discord-only, or both platforms at once.

> [!WARNING]
> This service can ask Codex to read and modify files or run commands on its host. Keep it private, use the generated pairing code, start with `safe` permission, and never expose the bot to unknown users.

## Features

- Private one-user pairing; no public HTTP port or webhook is required.
- Telegram long polling and Discord Gateway support.
- Multiple Git projects and multiple resumable Codex sessions per project.
- Photos and Discord file attachments.
- Live progress, cancellation, queued follow-up instructions, and token usage.
- Separate project, session, model, reasoning, and permission settings for Telegram and Discord.
- Safe defaults: workspace-only writes, no approval prompts, and bot secrets removed from every Codex child process.
- Optional Raspberry Pi extensions for systemd, controlled self-deployment, root tasks, Android builds, and artifact publishing.

Codex Relay uses the documented non-interactive `codex exec --json` interface and resumes sessions with `codex exec resume`. See the [official Codex CLI documentation](https://developers.openai.com/codex/cli).

## Requirements

- Python 3.10 or newer
- Git
- Codex CLI installed and authenticated (`codex login`)
- A Telegram bot token, a Discord bot token, or both

The relay reuses the Codex CLI login already stored on the host. Do not copy `~/.codex/auth.json` into this repository or share it with another user.

## Quick start

```bash
git clone https://github.com/yeonway/30_telegram_codex_bot.git
cd 30_telegram_codex_bot
python -m venv .venv
```

Activate the virtual environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and configure:

```bash
python -m pip install -e .
codex login
codex-relay-setup
codex-relay --env-file .env
```

The setup wizard asks for the platform token without echoing it, generates a pairing code, finds Codex on `PATH`, and creates a private `.env` file. It does not store the plain pairing code.

After the relay starts, send one of these in a private message:

```text
/pair YOUR_CODE     # Telegram
!pair YOUR_CODE     # Discord
```

Delete the pairing code from your notes after successful pairing. The paired account ID is kept in the private state file.

## Creating a bot

### Telegram

1. Open a chat with `@BotFather` and create a bot with `/newbot`.
2. Copy the bot token into the setup wizard.
3. Start the relay and DM the generated `/pair` command to your bot.

### Discord

1. Create an application and bot in the Discord Developer Portal.
2. Copy the bot token into the setup wizard.
3. Invite or DM the bot, then send the generated `!pair` command by DM.
4. For DM-only use, Message Content Intent is not required. To use one server channel, set `DISCORD_ALLOWED_CHANNEL_ID` and enable Message Content Intent.

The first Discord account that supplies the correct pairing code becomes the only allowed user. You can alternatively preconfigure `DISCORD_ALLOWED_USER_ID`.

## Commands

Telegram uses `/command`; Discord uses `!command`.

| Command | Purpose |
| --- | --- |
| `menu` / `panel` | Open the Telegram menu or Discord control panel |
| `projects`, `use NAME`, `where` | List, select, or show a project |
| `sessions`, `session new NAME`, `session NAME` | Manage resumable Codex sessions |
| `models`, `model NAME` | Inspect or override the Codex model |
| `intelligence LEVEL` | Set reasoning effort or return to `default` |
| `permission read\|safe\|auto` | Select the normal permission profile |
| `status`, `usage` | Show relay status and latest token usage |
| `steer TEXT` | Queue a follow-up after the current turn |
| `new` | Reset the selected Codex conversation |
| `cancel`, `cancel all` | Stop one or all running jobs |
| `help` | Show in-chat help |

`full`, `root`, and persistent `root always` require explicit confirmation. Root modes are a Raspberry Pi/Linux deployment extension and are unavailable on a normal Windows or macOS installation.

## Configuration

The wizard is recommended. For manual setup, copy [.env.example](.env.example) to `.env` and see [configuration.md](docs/configuration.md). Real `.env` files, state, credentials, backups, and local memory are ignored by Git.

`CODEX_PROJECT_ROOT` is a directory whose immediate child directories are Git repositories. This boundary prevents chat commands from selecting arbitrary folders elsewhere on the host. Explicit non-Git exceptions can be listed with `CODEX_EXTRA_PROJECTS`.

## Security model

- Pairing is accepted only in private messages.
- Only one Telegram user and one Discord user can control the relay.
- Bot tokens and pairing hashes are stripped from the Codex subprocess environment.
- Project names are validated and resolved below the configured project root.
- Downloads are size-limited; Discord attachments are accepted only from Discord CDN hosts.
- The default `safe` mode uses Codex workspace-write sandboxing with approvals disabled.
- `full` bypasses Codex sandboxing for one task. Use it only when the requested host-level operation is intentional.
- Pi root modes use a separately installed, tightly scoped launcher and are not part of portable setup.

This is a personal remote-administration tool, not a multi-tenant bot. Do not deploy it in a public channel or share one instance among untrusted users.

## Validation

```bash
python -m compileall app.py artifact_delivery.py codex_progress.py discord_bridge.py discord_controls.py relay_errors.py setup_relay.py tests
python -m unittest discover -s tests -v
```

GitHub Actions runs the test suite on Linux, macOS, and Windows with Python 3.10 and 3.12.

## Raspberry Pi service deployment

The original hardened Pi deployment remains available as an optional profile. It includes systemd, backups, delayed self-restart, root helpers, Android builds, and artifact publishing. See [Raspberry Pi deployment](docs/raspberry-pi.md).

## License

MIT
