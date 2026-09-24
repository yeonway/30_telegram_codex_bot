#!/usr/bin/env bash
set -euo pipefail

project=/home/user/Raspberry_Pi/30_telegram_codex_bot

first_output="$({
  codex exec --json --sandbox read-only -C "$project" \
    'Reply with exactly RESUME_FIRST_OK and nothing else.'
} 2>/dev/null)"

session_id="$(printf '%s\n' "$first_output" | python3 -c '
import json, sys
for line in sys.stdin:
    event = json.loads(line)
    if event.get("type") == "thread.started":
        print(event["thread_id"])
        break
')"

test -n "$session_id"

second_output="$({
  codex exec resume --json "$session_id" \
    'Reply with exactly RESUME_SECOND_OK and nothing else.'
} 2>/dev/null)"

answer="$(printf '%s\n' "$second_output" | python3 -c '
import json, sys
answer = ""
for line in sys.stdin:
    event = json.loads(line)
    item = event.get("item") or {}
    if event.get("type") == "item.completed" and item.get("type") == "agent_message":
        answer = item.get("text", "")
print(answer)
')"

test "$answer" = RESUME_SECOND_OK
printf '{"ok":true,"resume_smoke_ok":true}\n'

