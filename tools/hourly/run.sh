#!/usr/bin/env bash
# Hourly wrapper: run the refresh and log to logs/<UTC>.log
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DIR/logs"
/usr/bin/python3 "$DIR/refresh.py" "$@" > "$DIR/logs/$TS.log" 2>&1
cat "$DIR/logs/$TS.log"
exit 0
