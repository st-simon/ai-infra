#!/usr/bin/env bash
set -euo pipefail

LABEL="com.junxia.ai-infra.news-briefing"
TARGET_PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ -f "$TARGET_PLIST" ]]; then
  launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
  rm "$TARGET_PLIST"
  echo "Uninstalled launchd job: $LABEL"
else
  echo "No launchd plist found: $TARGET_PLIST"
fi
