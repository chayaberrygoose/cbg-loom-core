#!/bin/bash
# /* [FILE_ID]: fabricate_cron // VERSION: 1.1 // STATUS: STABLE */
# Wrapper script for cron execution of the CBG Fabrication Pipeline

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT" || exit 1

# Kill any stale fabricate.py processes (older than current run)
# Excludes the grep itself via pattern
OLD_PIDS=$(pgrep -f "scripts/fabricate.py" 2>/dev/null)
if [[ -n "$OLD_PIDS" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CLEANUP]: Killing stale processes: $OLD_PIDS" >> /tmp/cbg_fabricate.log
    pkill -f "scripts/fabricate.py" 2>/dev/null
    sleep 1
fi

# Activate venv and run fabrication
source .venv/bin/activate
python3 scripts/fabricate.py >> /tmp/cbg_fabricate.log 2>&1
