# Raspberry Pi deployment

This directory includes the project's original opinionated Raspberry Pi profile. Portable users do not need it.

## Installed layout

- Source: `/home/user/Raspberry_Pi/30_telegram_codex_bot`
- Runtime: `/srv/telegram-codex-bot`
- Secrets: `/etc/telegram-codex-bot.env` (`root:root`, mode `0600`)
- State: `/var/lib/telegram-codex-bot/state.json`
- Service: `telegram-codex-bot.service`
- Backups: `/srv/deploy-backups/telegram-codex-bot`

The profile also installs optional root, artifact-publishing, and Android-build helpers. Review every file under `deploy/` and adapt the hard-coded user and source paths before using it on a different Pi.

## Safe deployment rule

When deploying from inside the relay, never run a synchronous `systemctl restart telegram-codex-bot.service`: it terminates the process before the final chat response is delivered. Use the installed controlled deploy command instead:

```bash
/usr/local/sbin/telegram-codex-deploy
```

It creates a backup and schedules a detached restart after 45 seconds. Only this relay service is restarted.

## Verification

```bash
python3 -m compileall app.py tests
python3 -m unittest discover -s tests -v
bash deploy/verify_controls.sh
bash deploy/verify_parallel_sessions.sh
```

Never commit real bot tokens, pairing codes, numeric account IDs, Codex authentication files, or `/etc/telegram-codex-bot.env`.
