#!/usr/bin/env bash
set -euo pipefail

codex_binary="${CODEX_BINARY:-/usr/local/bin/codex}"
project="${CODEX_PROJECT:-/home/user/Raspberry_Pi/30_telegram_codex_bot}"
model="${CODEX_TEST_MODEL:-gpt-5.6-sol}"
first_output="$(mktemp)"
second_output="$(mktemp)"
trap 'rm -f "$first_output" "$second_output"' EXIT

run_check() {
  local expected="$1"
  local output="$2"
  printf 'Do not inspect or change files. Reply exactly %s.' "$expected" \
    | "$codex_binary" exec \
        --ephemeral \
        --json \
        --color never \
        -m "$model" \
        -c 'model_reasoning_effort="low"' \
        --sandbox read-only \
        -c 'approval_policy="never"' \
        -C "$project" \
        - >"$output"
}

run_check PARALLEL_SESSION_ONE_OK "$first_output" &
first_pid=$!
run_check PARALLEL_SESSION_TWO_OK "$second_output" &
second_pid=$!
wait "$first_pid"
wait "$second_pid"

grep -q 'PARALLEL_SESSION_ONE_OK' "$first_output"
grep -q 'PARALLEL_SESSION_TWO_OK' "$second_output"
printf '%s\n' PARALLEL_SESSION_ONE_OK PARALLEL_SESSION_TWO_OK
