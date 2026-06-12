#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.junxia.ai-infra.news-briefing"
SOURCE_PLIST="$PROJECT_ROOT/deploy/launchd/$LABEL.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$LABEL.plist"

mkdir -p "$TARGET_DIR"
mkdir -p "$PROJECT_ROOT/logs"

cp "$SOURCE_PLIST" "$TARGET_PLIST"
launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
launchctl load "$TARGET_PLIST"

echo "Installed launchd job: $LABEL"
echo "Plist: $TARGET_PLIST"
echo "Next run: daily at 07:00 local time"
