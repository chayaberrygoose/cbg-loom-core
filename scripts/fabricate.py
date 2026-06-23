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

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.fabricate_specimen_v2 import (
    fabricate_specimen,
    list_available_themes,
    select_remix_pair,
    select_least_used,
)
from scripts.generate_lore_from_news import run_lore_generation


def run(theme=None, base=None, breach=None, template=None, prompt=None, tile_scale=None, news=False):
    """
    Kick off a single fabrication run.

    Args:
        theme:    Use a single lore theme (legacy mode). Mutually exclusive with base/breach.
        base:     Explicit Base (Structure) lore name for remix.
        breach:   Explicit Breach (Interference) lore name for remix.
        template: Search string to filter garment templates (e.g. "Hoodie", "Joggers").
        prompt:   Manual prompt override — bypasses lore-driven generation.
        tile_scale: Tile pattern scale override. Larger = bigger tiles. None = use template default.
        news:     Enable Live News-driven Active Simulation mode (grabs news of the past hour,
                  synthesizes lore, and crafts the product).

    Returns:
        The created Printify product dict, or None on failure.
    """
    # Active Simulation: News-driven execution
    # If no explicit theme, remix base/breach, or manual prompt override is specified,
    # default to the live news-driven simulation.
    is_explicit = (theme is not None) or (base is not None) or (breach is not None) or (prompt is not None)
    if not is_explicit and not news:
        print("[SYSTEM_LOG]: No explicit layout/theme specified. Defaulting to Active Simulation (live news mode).")
        news = True

    if news:
        try:
            print("[SYSTEM_LOG]: 🌐 INITIATING ACTIVE SIMULATION — News Telemetry Ingestion starting …")
            news_theme, _ = run_lore_generation()
            print(f"[SYSTEM_LOG]: Lore synthesized: '{news_theme}'. Continuing with fabrication…")
            return fabricate_specimen(
                theme=news_theme,
                template_search=template,
                prompt_override=prompt,
                tile_scale=tile_scale,
            )
        except Exception as e:
            print(f"[SYSTEM_WARNING]: News lore synthesis failed / bypassed: {e}. Falling back to standard pool.")

    available = list_available_themes()
    if not available:
        print("[SYSTEM_ERROR]: No lore files in artifacts/lore/. Cannot fabricate.")
        return None

    # Single-theme legacy path (explicit)
    if theme:
        return fabricate_specimen(theme=theme, template_search=template, prompt_override=prompt, tile_scale=tile_scale)

    # Explicit remix path (base/breach specified)
    if base or breach:
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
            tile_scale=tile_scale,
        )

    # Random mode selection: 50/50 remix vs single theme
    if random.choice([True, False]):
        # Remix Protocol — usage-weighted pair selection
        base_name, breach_name, remix_desc = select_remix_pair()
        display = f"{base_name} x {breach_name}"
        print(f"[SYSTEM_LOG]: Random mode selected REMIX — {display}")
        return fabricate_specimen(
            theme=display,
            template_search=template,
            prompt_override=prompt,
            base_name=base_name,
            breach_name=breach_name,
            remix_desc=remix_desc,
            tile_scale=tile_scale,
        )
    else:
        # Single theme — usage-weighted selection (least-used first)
        picks = select_least_used(available, count=1)
        theme = picks[0]
        print(f"[SYSTEM_LOG]: Random mode selected SINGLE THEME — {theme}")
        return fabricate_specimen(theme=theme, template_search=template, prompt_override=prompt, tile_scale=tile_scale)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CBG Fabrication — simple entry point")
    parser.add_argument("--theme", help="Single lore theme (legacy mode)")
    parser.add_argument("--base", help="Remix Base lore name")
    parser.add_argument("--breach", help="Remix Breach lore name")
    parser.add_argument("--template", help="Filter garment template (e.g. 'Hoodie')")
    parser.add_argument("--prompt", help="Manual prompt override")
    parser.add_argument("--tile-scale", type=float, default=1.0, help="Tile pattern scale (default: 1.0). Larger = bigger tiles.")
    parser.add_argument("--news", action="store_true", help="Synthesize lore from live news and fabricate")
    args = parser.parse_args()

    result = run(
        theme=args.theme,
        base=args.base,
        breach=args.breach,
        template=args.template,
        prompt=args.prompt,
        tile_scale=args.tile_scale,
        news=args.news,
    )
    sys.exit(0 if result else 1)
