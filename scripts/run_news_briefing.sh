#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" "$PROJECT_ROOT/agents/news_briefing/agent.py"

gmail_api_mode="${AI_INFRA_GMAIL_API_DRAFT_ENABLED:-auto}"
case "$gmail_api_mode" in
  0|false|False|FALSE|no|No|NO|off|Off|OFF)
    exit 0
    ;;
esac

gmail_api_attempts="${AI_INFRA_GMAIL_API_DRAFT_ATTEMPTS:-3}"
gmail_api_retry_seconds="${AI_INFRA_GMAIL_API_DRAFT_RETRY_SECONDS:-120}"
attempt=1

while true; do
  if "$PYTHON_BIN" \
    "$PROJECT_ROOT/scripts/gmail_api_create_draft_from_request.py" \
    --latest; then
    break
  fi

  if (( attempt >= gmail_api_attempts )); then
    exit 1
  fi

  echo "Gmail API draft creation failed; retrying in ${gmail_api_retry_seconds}s (${attempt}/${gmail_api_attempts})" >&2
  sleep "$gmail_api_retry_seconds"
  attempt=$((attempt + 1))
done
