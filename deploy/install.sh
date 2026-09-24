#!/usr/bin/env bash
set -euo pipefail

source_dir=/home/user/Raspberry_Pi/30_telegram_codex_bot
runtime_dir=/srv/telegram-codex-bot
unit_path=/etc/systemd/system/telegram-codex-bot.service
env_path=/etc/telegram-codex-bot.env
root_runner_path=/usr/local/sbin/telegram-codex-root
deploy_runner_path=/usr/local/sbin/telegram-codex-deploy
publisher_path=/usr/local/sbin/telegram-codex-publish-artifact
android_builder_path=/usr/local/bin/android-build-apk
skills_root=/home/user/.codex/skills
sudoers_path=/etc/sudoers.d/telegram-codex-bot-root
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="/srv/deploy-backups/telegram-codex-bot/$stamp"

test -f "$source_dir/app.py"
test -f "$source_dir/codex_progress.py"
test -f "$source_dir/artifact_delivery.py"
test -f "$source_dir/discord_bridge.py"
test -f "$source_dir/discord_controls.py"
test -f "$source_dir/relay_errors.py"
test -f "$source_dir/requirements.txt"
test -f "$source_dir/deploy/telegram-codex-bot.service"
test -f "$source_dir/deploy/telegram-codex-root"
test -f "$source_dir/deploy/telegram-codex-deploy"
test -f "$source_dir/deploy/telegram-codex-publish-artifact"
test -f "$source_dir/deploy/android-build-apk"
test -f "$source_dir/deploy/telegram-codex-bot.sudoers"
test -f "$env_path"
bash -n "$source_dir/deploy/telegram-codex-root"
bash -n "$source_dir/deploy/telegram-codex-deploy"
bash -n "$source_dir/deploy/android-build-apk"
python3 -m py_compile "$source_dir/deploy/telegram-codex-publish-artifact"

sudo install -d -m 700 "$backup_dir"
if [ -d "$runtime_dir" ]; then
  sudo cp -a "$runtime_dir" "$backup_dir/runtime"
fi
if [ -f "$unit_path" ]; then
  sudo cp -a "$unit_path" "$backup_dir/telegram-codex-bot.service"
fi
if [ -f "$root_runner_path" ]; then
  sudo cp -a "$root_runner_path" "$backup_dir/telegram-codex-root"
fi
if [ -f "$deploy_runner_path" ]; then
  sudo cp -a "$deploy_runner_path" "$backup_dir/telegram-codex-deploy"
fi
if [ -f "$publisher_path" ]; then
  sudo cp -a "$publisher_path" "$backup_dir/telegram-codex-publish-artifact"
fi
if [ -f "$android_builder_path" ]; then
  sudo cp -a "$android_builder_path" "$backup_dir/android-build-apk"
fi
for skill in pi-android-apk-build pi-drive-artifact-release pi-remote-codex-ops; do
  if [ -d "$skills_root/$skill" ]; then
    sudo install -d -m 700 "$backup_dir/skills"
    sudo cp -a "$skills_root/$skill" "$backup_dir/skills/"
  fi
done
if [ -f "$sudoers_path" ]; then
  sudo cp -a "$sudoers_path" "$backup_dir/telegram-codex-bot-root.sudoers"
fi
sudo stat -c '%U:%G %a %n' "$env_path" | sudo tee "$backup_dir/env-metadata.txt" >/dev/null

sudo install -d -o root -g root -m 755 "$runtime_dir"
sudo install -o root -g root -m 755 "$source_dir/app.py" "$runtime_dir/app.py"
sudo install -o root -g root -m 644 "$source_dir/codex_progress.py" "$runtime_dir/codex_progress.py"
sudo install -o root -g root -m 644 "$source_dir/artifact_delivery.py" "$runtime_dir/artifact_delivery.py"
sudo install -o root -g root -m 644 "$source_dir/discord_bridge.py" "$runtime_dir/discord_bridge.py"
sudo install -o root -g root -m 644 "$source_dir/discord_controls.py" "$runtime_dir/discord_controls.py"
sudo install -o root -g root -m 644 "$source_dir/relay_errors.py" "$runtime_dir/relay_errors.py"
sudo install -o root -g root -m 644 "$source_dir/requirements.txt" "$runtime_dir/requirements.txt"
if [ ! -x "$runtime_dir/venv/bin/python" ]; then
  sudo python3 -m venv "$runtime_dir/venv"
fi
sudo "$runtime_dir/venv/bin/python" -m pip install --disable-pip-version-check \
  --requirement "$runtime_dir/requirements.txt"
sudo install -o root -g root -m 644 \
  "$source_dir/deploy/telegram-codex-bot.service" "$unit_path"
sudo install -o root -g root -m 755 \
  "$source_dir/deploy/telegram-codex-root" "$root_runner_path"
sudo install -o root -g root -m 755 \
  "$source_dir/deploy/telegram-codex-deploy" "$deploy_runner_path"
sudo install -o root -g root -m 755 \
  "$source_dir/deploy/telegram-codex-publish-artifact" "$publisher_path"
sudo install -o root -g root -m 755 \
  "$source_dir/deploy/android-build-apk" "$android_builder_path"
sudo install -d -o user -g user -m 700 /var/lib/telegram-codex-bot/artifacts
sudo install -d -o user -g user -m 700 /var/cache/telegram-codex-bot/gradle
sudo chmod -R a+rX /opt/android-sdk /opt/aapt2 /opt/aapt2-x86-root
for skill in pi-android-apk-build pi-drive-artifact-release pi-remote-codex-ops; do
  sudo install -d -o user -g user -m 755 "$skills_root/$skill/agents"
  sudo install -o user -g user -m 644 "$source_dir/skills/$skill/SKILL.md" "$skills_root/$skill/SKILL.md"
  sudo install -o user -g user -m 644 "$source_dir/skills/$skill/agents/openai.yaml" "$skills_root/$skill/agents/openai.yaml"
done
sudo install -o root -g root -m 440 \
  "$source_dir/deploy/telegram-codex-bot.sudoers" "$sudoers_path"
sudo visudo -cf "$sudoers_path"
sudo -n "$root_runner_path" --version

sudo systemd-analyze verify "$unit_path"
sudo systemctl daemon-reload
sudo systemctl enable telegram-codex-bot.service
restart_unit="telegram-codex-bot-restart-${stamp}-$$"
sudo systemd-run \
  --quiet \
  --no-block \
  --collect \
  --unit="$restart_unit" \
  --on-active=45s \
  /bin/systemctl restart telegram-codex-bot.service

echo "BACKUP=$backup_dir"
echo "RESTART_SCHEDULED=$restart_unit"
systemctl is-enabled telegram-codex-bot.service
systemctl is-active telegram-codex-bot.service
