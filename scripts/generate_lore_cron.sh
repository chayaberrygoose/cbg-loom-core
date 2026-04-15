#!/bin/bash
# /* [FILE_ID]: generate_lore_cron // VERSION: 2.0 // STATUS: STABLE */
# Wrapper for cron execution of the lore generation pipeline.
# Uses a lockfile to prevent overlapping runs.

LOCKFILE="/tmp/cbg_lore_gen.lock"

if [[ -f "$LOCKFILE" ]]; then
    # Check if the PID in the lockfile is still alive
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SKIP]: Previous lore run (PID $OLD_PID) still active. Deferring." >> /tmp/cbg_lore_gen.log
        exit 0
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CLEANUP]: Stale lock from PID $OLD_PID. Removing." >> /tmp/cbg_lore_gen.log
        rm -f "$LOCKFILE"
    fi
fi

# Acquire lock
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd ~/repos/cbg-loom-core || exit 1
source .venv/bin/activate
python scripts/generate_lore_from_comments.py >> /tmp/cbg_lore_gen.log 2>&1
