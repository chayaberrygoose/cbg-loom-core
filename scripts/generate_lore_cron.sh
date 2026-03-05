#!/bin/bash
cd ~/repos/cbg-loom-core || exit 1
source .venv/bin/activate
python scripts/generate_lore_from_comments.py --max-comments 3
