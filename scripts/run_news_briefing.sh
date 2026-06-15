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

"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/agents/news_briefing/agent.py"

gmail_api_mode="${AI_INFRA_GMAIL_API_DRAFT_ENABLED:-auto}"
case "$gmail_api_mode" in
  0|false|False|FALSE|no|No|NO|off|Off|OFF)
    exit 0
    ;;
esac

"$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/scripts/gmail_api_create_draft_from_request.py" \
  --latest
