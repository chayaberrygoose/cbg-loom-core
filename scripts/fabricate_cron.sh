#!/bin/bash
# /* [FILE_ID]: fabricate_cron // VERSION: 1.0 // STATUS: STABLE */
# Wrapper script for cron execution of the CBG Fabrication Pipeline

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT" || exit 1

# Activate venv and run fabrication
source .venv/bin/activate
python3 scripts/fabricate.py >> /tmp/cbg_fabricate.log 2>&1
