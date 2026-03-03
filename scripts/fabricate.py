#!/usr/bin/env python3
"""
/* [FILE_ID]: fabricate // VERSION: 1.0 // STATUS: STABLE */

Simple entry point for the CBG fabrication pipeline.
Creates one UNVERIFIED SPECIMEN product + blog post.

Usage:
    # Zero-config — random remix combo, random template:
    python3 scripts/fabricate.py

    # Pick a specific remix pair:
    python3 scripts/fabricate.py --base "Obsidian Circuit" --breach "Thermal Breach"

    # Pick a specific garment template:
    python3 scripts/fabricate.py --template "Hoodie"

    # Single lore theme (legacy mode):
    python3 scripts/fabricate.py --theme "Phantom Grid"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.fabricate_specimen_v2 import (
    fabricate_specimen,
    list_available_themes,
    select_remix_pair,
)


def run(theme=None, base=None, breach=None, template=None, prompt=None):
    """
    Kick off a single fabrication run.

    Args:
        theme:    Use a single lore theme (legacy mode). Mutually exclusive with base/breach.
        base:     Explicit Base (Structure) lore name for remix.
        breach:   Explicit Breach (Interference) lore name for remix.
        template: Search string to filter garment templates (e.g. "Hoodie", "Joggers").
        prompt:   Manual prompt override — bypasses lore-driven generation.

    Returns:
        The created Printify product dict, or None on failure.
    """
    available = list_available_themes()
    if not available:
        print("[SYSTEM_ERROR]: No lore files in artifacts/lore/. Cannot fabricate.")
        return None

    # Single-theme legacy path
    if theme:
        return fabricate_specimen(theme=theme, template_search=template, prompt_override=prompt)

    # Remix Protocol (default)
    base_name, breach_name, remix_desc = select_remix_pair(
        base_override=base, breach_override=breach
    )
    display = f"{base_name} x {breach_name}"
    return fabricate_specimen(
        theme=display,
        template_search=template,
        prompt_override=prompt,
        base_name=base_name,
        breach_name=breach_name,
        remix_desc=remix_desc,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CBG Fabrication — simple entry point")
    parser.add_argument("--theme", help="Single lore theme (legacy mode)")
    parser.add_argument("--base", help="Remix Base lore name")
    parser.add_argument("--breach", help="Remix Breach lore name")
    parser.add_argument("--template", help="Filter garment template (e.g. 'Hoodie')")
    parser.add_argument("--prompt", help="Manual prompt override")
    args = parser.parse_args()

    result = run(
        theme=args.theme,
        base=args.base,
        breach=args.breach,
        template=args.template,
        prompt=args.prompt,
    )
    sys.exit(0 if result else 1)
