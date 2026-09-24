#!/usr/bin/env bash
set -euo pipefail

codex_binary="${CODEX_BINARY:-/usr/local/bin/codex}"
project="${CODEX_PROJECT:-/home/user/Raspberry_Pi/30_telegram_codex_bot}"
model="${CODEX_TEST_MODEL:-gpt-5.6-sol}"
intelligence="${CODEX_TEST_INTELLIGENCE:-low}"
new_output="$(mktemp)"
resume_output="$(mktemp)"
auto_output="$(mktemp)"
full_output="$(mktemp)"
trap 'rm -f "$new_output" "$resume_output" "$auto_output" "$full_output"' EXIT

printf '%s' 'Do not inspect or change files. Reply exactly CONTROL_SAFE_OK.' \
  | "$codex_binary" exec \
      --json \
      --color never \
      -m "$model" \
      -c "model_reasoning_effort=\"$intelligence\"" \
      --sandbox workspace-write \
      -c 'approval_policy="never"' \
      -C "$project" \
      - >"$new_output"

grep -q 'CONTROL_SAFE_OK' "$new_output"
session_id="$(jq -r 'select(.type == "thread.started") | .thread_id' "$new_output" | head -n 1)"
test -n "$session_id"

cd "$project"
printf '%s' 'Do not inspect or change files. Reply exactly CONTROL_RESUME_READ_OK.' \
  | "$codex_binary" exec resume \
      --json \
      -m "$model" \
      -c "model_reasoning_effort=\"$intelligence\"" \
      -c 'sandbox_mode="read-only"' \
      -c 'approval_policy="never"' \
      "$session_id" \
      - >"$resume_output"

grep -q 'CONTROL_RESUME_READ_OK' "$resume_output"

printf '%s' 'Run curl -fsS https://example.com without writing files. If it succeeds, reply exactly CONTROL_AUTO_REVIEW_OK.' \
  | "$codex_binary" exec \
      --json \
      --color never \
      -m "$model" \
      -c "model_reasoning_effort=\"$intelligence\"" \
      --sandbox workspace-write \
      -c 'approval_policy="on-request"' \
      -c 'approvals_reviewer="auto_review"' \
      -C "$project" \
      - >"$auto_output"

grep -q 'CONTROL_AUTO_REVIEW_OK' "$auto_output"

printf '%s' 'Do not inspect or change files. Reply exactly CONTROL_FULL_OK.' \
  | "$codex_binary" exec \
      --json \
      --color never \
      -m "$model" \
      -c "model_reasoning_effort=\"$intelligence\"" \
      --dangerously-bypass-approvals-and-sandbox \
      -C "$project" \
      - >"$full_output"

grep -q 'CONTROL_FULL_OK' "$full_output"
printf '%s\n' \
  "CONTROL_SAFE_OK" \
  "CONTROL_RESUME_READ_OK" \
  "CONTROL_AUTO_REVIEW_OK" \
  "CONTROL_FULL_OK"
