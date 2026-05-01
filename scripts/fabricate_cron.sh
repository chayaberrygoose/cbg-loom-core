#!/bin/bash
# /* [FILE_ID]: fabricate_cron // VERSION: 2.0 // STATUS: STABLE */
# Wrapper script for cron execution of the CBG Fabrication Pipeline
# Includes pre/post git sync — fails gracefully, never blocks fabrication.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG="/tmp/cbg_fabricate.log"

cd "$PROJECT_ROOT" || exit 1

# ── Git Sync Helper ─────────────────────────────────────────────
# Graceful: logs outcome but never aborts the pipeline.
git_pre_sync() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Pre-run pull starting..." >> "$LOG"

    # Stash any uncommitted local changes, pull with rebase, then pop stash
    local stash_depth_before
    stash_depth_before=$(git stash list 2>/dev/null | wc -l)
    git stash --include-untracked -q 2>/dev/null
    local stash_depth_after
    stash_depth_after=$(git stash list 2>/dev/null | wc -l)
    local stashed=$(( stash_depth_after - stash_depth_before ))

    if git pull --rebase --no-edit origin main >> "$LOG" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Pull succeeded." >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Pull failed or conflict — aborting rebase, continuing with local state." >> "$LOG"
        git rebase --abort 2>/dev/null
    fi

    # Restore stashed changes if we stashed anything
    if [[ $stashed -gt 0 ]]; then
        git stash pop -q 2>/dev/null || {
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Stash pop conflict — keeping stash, continuing." >> "$LOG"
            git checkout -- . 2>/dev/null
        }
    fi
}

git_post_sync() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Post-run commit+push starting..." >> "$LOG"

    # Stage all tracked changes (gitignore keeps graphics out)
    git add -A 2>/dev/null

    # Only commit if there are staged changes
    if git diff --cached --quiet 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Nothing to commit." >> "$LOG"
        return 0
    fi

    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M')"
    git commit -q -m "auto: fabrication run ${timestamp}" >> "$LOG" 2>&1

    if git push -q origin main >> "$LOG" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Push succeeded." >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GIT_SYNC]: Push failed — changes committed locally, will retry next run." >> "$LOG"
    fi
}

# ── Kill Stale Processes ────────────────────────────────────────
OLD_PIDS=$(pgrep -f "scripts/fabricate.py" 2>/dev/null)
if [[ -n "$OLD_PIDS" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CLEANUP]: Killing stale processes: $OLD_PIDS" >> "$LOG"
    pkill -f "scripts/fabricate.py" 2>/dev/null
    sleep 1
fi

# ── Activate venv ───────────────────────────────────────────────
source .venv/bin/activate

# ── PRE-SYNC: pull latest logic ────────────────────────────────
git_pre_sync

# ── FABRICATION RUN ─────────────────────────────────────────────
python3 scripts/fabricate.py >> "$LOG" 2>&1

# ── POST-SYNC: commit + push any tracked changes ───────────────
git_post_sync
