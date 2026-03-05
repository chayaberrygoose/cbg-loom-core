#!/usr/bin/env python3
# [FILE_ID]: scripts/RANDOM_DRAFT // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: AUTOMATED_DRAFT_TEMPLATE_GENERATION
"""
Automatically creates draft templates from random unused blueprints.

Picks random unused AOP blueprints, selects random graphics from available
tiles/textures/logos, and creates [DRAFT] products in Printify.

Usage:
    # Create a random draft template
    python3 scripts/random_draft.py

    # Create multiple random drafts (pulls products once, creates N drafts)
    python3 scripts/random_draft.py --count 5

    # Dry run (show what would be created)
    python3 scripts/random_draft.py --dry-run

    # Force specific graphics
    python3 scripts/random_draft.py --tile path/to/tile.png --texture path/to/texture.png
"""

import sys
import os
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts.blueprint_explorer import BlueprintExplorer


def find_graphics(base_dir: Path) -> list:
    """Recursively finds all PNG files in a directory."""
    return list(base_dir.rglob("*.png"))


def pick_random_graphic(graphics_dir: str, category: str) -> str:
    """Picks a random PNG from a graphics directory."""
    base = Path(graphics_dir)
    if not base.exists():
        print(f"!! [SYSTEM_WARNING]: {category} directory not found: {graphics_dir}")
        return None
    
    pngs = find_graphics(base)
    if not pngs:
        print(f"!! [SYSTEM_WARNING]: No PNGs found in {category} directory")
        return None
    
    selected = random.choice(pngs)
    print(f"// SELECTED_{category.upper()}: {selected.name}")
    return str(selected)


def main():
    parser = argparse.ArgumentParser(description="Create random draft template from unused blueprint")
    parser.add_argument("--count", "-n", type=int, default=1, help="Number of drafts to create (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without creating")
    parser.add_argument("--tile", type=str, help="Override tile selection with specific path")
    parser.add_argument("--texture", type=str, help="Override texture selection with specific path")
    parser.add_argument("--logo", type=str, help="Override logo selection with specific path")
    parser.add_argument("--price", type=int, default=4500, help="Price in cents (default: 4500)")
    
    args = parser.parse_args()
    
    # Base paths
    workspace = Path(__file__).resolve().parent.parent
    tiles_dir = workspace / "artifacts" / "graphics" / "tiles"
    textures_dir = workspace / "artifacts" / "graphics" / "textures"
    logos_dir = workspace / "artifacts" / "graphics" / "logos"
    
    print("[SYSTEM_LOG]: RANDOM_DRAFT_GENERATOR // INITIALIZING")
    print("=" * 60)
    
    # Initialize explorer
    explorer = BlueprintExplorer()
    
    # Get unused blueprints (pulled once upfront)
    print("\n// SCANNING_SHOP for used blueprints...")
    used = explorer.get_used_blueprint_ids()
    blueprints = explorer.list_aop_blueprints()
    unused = [b for b in blueprints if b['id'] not in used]
    
    if not unused:
        print("!! [SYSTEM_FAILURE]: No unused AOP blueprints available!")
        print(f"   All {len(blueprints)} AOP blueprints are already in use.")
        return 1
    
    print(f"// FOUND: {len(unused)} unused AOP blueprints (out of {len(blueprints)} total)")
    
    # Adjust count if more than available
    count = min(args.count, len(unused))
    if count < args.count:
        print(f"// [SYSTEM_WARNING]: Requested {args.count}, but only {len(unused)} unused blueprints available.")
    
    print(f"// CREATING: {count} draft(s)")
    
    created = 0
    failed = 0
    
    for i in range(count):
        print(f"\n{'=' * 60}")
        print(f"[DRAFT {i + 1}/{count}]")
        print("=" * 60)
        
        # Pick random blueprint from remaining unused
        selected_bp = random.choice(unused)
        unused.remove(selected_bp)  # Remove so we don't pick it again
        
        print(f"\n--- SELECTED_BLUEPRINT ---")
        print(f"    ID: {selected_bp['id']}")
        print(f"    Title: {selected_bp['title']}")
        
        # Inspect for more details
        info = explorer.inspect_blueprint(selected_bp['id'])
        if info['providers']:
            provider = info['providers'][0]
            print(f"    Provider: [{provider['id']}] {provider['title']}")
            print(f"    Variants: {provider['variant_count']}")
        
        positions = explorer.get_known_positions(selected_bp['id'])
        print(f"    Positions: {positions}")
        
        # Select graphics (random each time unless overridden)
        print(f"\n--- SELECTING_GRAPHICS ---")
        tile_path = args.tile or pick_random_graphic(str(tiles_dir), "tile")
        texture_path = args.texture or pick_random_graphic(str(textures_dir), "texture")
        
        # Always use QR code for logo
        qr_path = logos_dir / "repo_portal_qr.png"
        logo_path = args.logo or str(qr_path)
        print(f"// SELECTED_LOGO: {Path(logo_path).name}")
        
        if args.dry_run:
            print(f"\n[DRY_RUN]: Would create template with:")
            print(f"    Blueprint: [{selected_bp['id']}] {selected_bp['title']}")
            print(f"    Tile: {tile_path}")
            print(f"    Texture: {texture_path}")
            print(f"    Logo: {logo_path}")
            print(f"    Price: ${args.price / 100:.2f}")
            created += 1
            continue
        
        # Create the template
        print(f"\n--- CREATING_TEMPLATE ---")
        try:
            product = explorer.create_template(
                blueprint_id=selected_bp['id'],
                tile_path=tile_path,
                texture_path=texture_path,
                logo_path=logo_path,
                provider_id=None,  # Auto-detect
                price_cents=args.price
            )
            
            print(f"\n[SIGNAL_STABLE]: Draft template created successfully!")
            print(f"// CONDUIT: https://printify.com/app/store/{explorer.shop_id}/products/{product['id']}")
            created += 1
            
        except Exception as e:
            print(f"\n!! [SYSTEM_FAILURE]: {e}")
            failed += 1
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"[SUMMARY] Created: {created} | Failed: {failed}")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
