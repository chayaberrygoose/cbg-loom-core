#!/usr/bin/env python3
# [FILE_ID]: scripts/BLUEPRINT_EXPLORER // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: PRINTIFY_BLUEPRINT_CATALOG_INTERFACE
"""
Explore Printify AOP blueprints and create templates from scratch.

Usage:
    # List all AOP blueprints
    python3 scripts/blueprint_explorer.py --list

    # Inspect a specific blueprint
    python3 scripts/blueprint_explorer.py --inspect 281

    # Create a template from blueprint
    python3 scripts/blueprint_explorer.py --create 281 --tile path/to/tile.png --texture path/to/texture.png --logo path/to/logo.png
"""

import sys
import os
import json
import argparse
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()


class BlueprintExplorer:
    BASE_URL = "https://api.printify.com/v1"

    def __init__(self):
        self.token = os.getenv("PRINTIFY_API_KEY") or os.getenv("printify_api_key")
        self.shop_id = os.getenv("PRINTIFY_SHOP_ID")
        if not self.token:
            raise ValueError("PRINTIFY_API_KEY not set")
        if not self.shop_id:
            raise ValueError("PRINTIFY_SHOP_ID not set")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def list_aop_blueprints(self) -> list:
        """Lists all AOP blueprints from the Printify catalog."""
        resp = requests.get(f"{self.BASE_URL}/catalog/blueprints.json", headers=self.headers)
        resp.raise_for_status()
        blueprints = resp.json()
        return [b for b in blueprints if "AOP" in b.get("title", "") or "All Over" in b.get("title", "")]

    def get_used_blueprint_ids(self) -> set:
        """
        Returns set of blueprint IDs already in use in the shop.
        Only considers products with [DRAFT] or [TEMPLATE] in the title
        and excludes deleted products.
        """
        resp = requests.get(f"{self.BASE_URL}/shops/{self.shop_id}/products.json", headers=self.headers)
        resp.raise_for_status()
        products = resp.json().get("data", [])
        
        used = set()
        for p in products:
            title = p.get("title", "")
            # Only consider [DRAFT] or [TEMPLATE] products
            if "[DRAFT]" not in title and "[TEMPLATE]" not in title:
                continue
            
            resp2 = requests.get(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{p['id']}.json",
                headers=self.headers
            )
            if resp2.status_code == 200:
                product_data = resp2.json()
                # Skip deleted products
                if product_data.get("is_deleted", False):
                    continue
                if not product_data.get("visible", True):
                    continue
                bp_id = product_data.get("blueprint_id")
                if bp_id:
                    used.add(bp_id)
        return used

    def get_blueprint(self, blueprint_id: int) -> dict:
        """Gets blueprint details."""
        resp = requests.get(f"{self.BASE_URL}/catalog/blueprints/{blueprint_id}.json", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def get_print_providers(self, blueprint_id: int) -> list:
        """Gets available print providers for a blueprint."""
        resp = requests.get(
            f"{self.BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers.json",
            headers=self.headers
        )
        resp.raise_for_status()
        return resp.json()

    def get_variants(self, blueprint_id: int, provider_id: int) -> list:
        """Gets variants (sizes/colors) for a blueprint+provider combo."""
        resp = requests.get(
            f"{self.BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json",
            headers=self.headers
        )
        resp.raise_for_status()
        return resp.json().get("variants", [])

    def upload_image(self, local_path: str, file_name: str) -> str:
        """Uploads an image to Printify and returns the image ID."""
        import base64
        with open(local_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        payload = {"file_name": file_name, "contents": data}
        resp = requests.post(f"{self.BASE_URL}/uploads/images.json", json=payload, headers=self.headers)
        resp.raise_for_status()
        return resp.json()["id"]

    def inspect_blueprint(self, blueprint_id: int) -> dict:
        """Gets comprehensive info about a blueprint."""
        bp = self.get_blueprint(blueprint_id)
        providers = self.get_print_providers(blueprint_id)

        info = {
            "id": blueprint_id,
            "title": bp.get("title"),
            "description": bp.get("description", "")[:200],
            "brand": bp.get("brand"),
            "providers": []
        }

        for p in providers:
            variants = self.get_variants(blueprint_id, p["id"])
            info["providers"].append({
                "id": p["id"],
                "title": p["title"],
                "variant_count": len(variants),
                "sample_variants": variants[:3]
            })

        return info

    def get_positions_from_api(self, blueprint_id: int, provider_id: int) -> list:
        """
        Fetches actual placeholder positions from the Printify API.
        Extracts unique positions from variant placeholders.
        """
        resp = requests.get(
            f"{self.BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json",
            headers=self.headers
        )
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        variants = data.get("variants", [])
        
        # Collect unique positions from all variants
        positions = set()
        for v in variants:
            for ph in v.get("placeholders", []):
                pos = ph.get("position")
                if pos:
                    positions.add(pos)
        
        return list(positions)

    def get_known_positions(self, blueprint_id: int) -> list:
        """
        Returns known placeholder positions for common AOP blueprints.
        This is based on examination of existing products.
        """
        positions = {
            256: ["front", "back", "all", "waistband"],  # Women's Leggings
            276: ["front", "back", "all"],  # Women's Racerback Dress
            279: ["front", "back", "all", "right_sleeve", "left_sleeve"],  # Women's Tee
            281: ["front", "back", "all", "right_sleeve", "left_sleeve", "Collar"],  # Unisex Tee
            285: ["front", "back", "all", "waistband"],  # Pencil Skirt
            286: ["front", "back", "all", "waistband"],  # Skater Skirt
            349: ["front", "back", "all"],  # Bikini
            350: ["front", "back", "all"],  # One-piece Swimsuit
            406: ["front", "back", "all", "waistband"],  # Men's Boxer
            407: ["front", "back", "all", "waistband"],  # Women's Briefs
            431: ["front", "back", "all"],  # T-Shirt Dress
            433: ["front", "back", "all", "right_sleeve", "left_sleeve"],  # Bomber Jacket
            449: ["front", "back", "all", "right_sleeve", "left_sleeve"],  # Sweatshirt
            450: ["front", "back", "all", "pocket", "waistband", "right_sleeve", "left_sleeve",
                  "right_cuff_panel", "left_cuff_panel", "right_hood", "left_hood"],  # Pullover Hoodie
            451: ["front_left", "front_right", "back", "all", "pocket_left", "pocket_right",
                  "waistband", "right_sleeve", "left_sleeve", "right_cuff_panel",
                  "left_cuff_panel", "right_hood", "left_hood"],  # Zip Hoodie
            516: ["left_leg", "right_leg", "all", "front_waistband", "back_waistband", "gusset"],  # Yoga Leggings
            591: ["left_leg", "right_leg", "pocket", "waistband"],  # Athletic Joggers
            700: ["front", "back", "all"],  # Sports Bra
            925: ["front_left_leg", "front_right_leg", "back_left_leg", "back_right_leg", "waistband"],  # Relaxed Shorts
        }
        return positions.get(blueprint_id, ["front", "back", "all"])

    def create_template(
        self,
        blueprint_id: int,
        tile_path: str = None,
        texture_path: str = None,
        logo_path: str = None,
        provider_id: int = None,  # Auto-detect if not specified
        price_cents: int = 4500
    ) -> dict:
        """
        Creates a new [DRAFT] product from a blueprint.

        Args:
            blueprint_id: Printify blueprint ID
            tile_path: Path to tiled pattern image (for body)
            texture_path: Path to texture image (for trim)
            logo_path: Path to logo image
            provider_id: Print provider ID (auto-detected if not specified)
            price_cents: Price in cents (default: $45.00)
        """
        bp = self.get_blueprint(blueprint_id)
        
        # Auto-detect provider if not specified
        if provider_id is None:
            providers = self.get_print_providers(blueprint_id)
            if not providers:
                raise ValueError(f"No print providers available for blueprint {blueprint_id}")
            provider_id = providers[0]["id"]
            print(f"[SYSTEM_LOG]: Auto-selected provider [{provider_id}] {providers[0].get('title', 'Unknown')}")
        
        variants = self.get_variants(blueprint_id, provider_id)
        
        # Get actual positions from API
        positions = self.get_positions_from_api(blueprint_id, provider_id)
        if not positions:
            print(f"[SYSTEM_WARNING]: No positions from API, using fallback")
            positions = self.get_known_positions(blueprint_id)

        print(f"[SYSTEM_LOG]: Creating template from Blueprint [{blueprint_id}] {bp['title']}")
        print(f"[SYSTEM_LOG]: Provider ID: {provider_id}, Variants: {len(variants)}")
        print(f"[SYSTEM_LOG]: Available positions: {positions}")

        # Upload images
        tile_id = None
        texture_id = None
        logo_id = None

        if tile_path and Path(tile_path).exists():
            print(f"// UPLOADING_TILE: {tile_path}")
            tile_id = self.upload_image(tile_path, f"template_tile_{blueprint_id}.png")

        if texture_path and Path(texture_path).exists():
            print(f"// UPLOADING_TEXTURE: {texture_path}")
            texture_id = self.upload_image(texture_path, f"template_texture_{blueprint_id}.png")

        if logo_path and Path(logo_path).exists():
            print(f"// UPLOADING_LOGO: {logo_path}")
            logo_id = self.upload_image(logo_path, f"template_logo_{blueprint_id}.png")

        # Build print_areas - apply tiled pattern to ALL positions from API
        placeholders = []
        
        # Identify a "front" position for logo placement
        front_positions = {"front", "front_left", "front_right", "front_left_leg", "front_right_leg"}
        logo_position = None
        for pos in positions:
            if pos in front_positions:
                logo_position = pos
                break
        # Fallback: use first position if no "front" found
        if not logo_position and positions:
            logo_position = positions[0]

        if tile_id:
            for pos in positions:
                images = [{
                    "id": tile_id,
                    "x": 0.5,
                    "y": 0.5,
                    "scale": 0.25,
                    "angle": 0,
                    "pattern": {
                        "spacing_x": 1,
                        "spacing_y": 1,
                        "angle": 0,
                        "offset": 0
                    }
                }]
                
                # Add logo to the front position
                if logo_id and pos == logo_position:
                    images.append({
                        "id": logo_id,
                        "x": 0.5,
                        "y": 0.35,
                        "scale": 0.12,
                        "angle": 0
                    })
                    print(f"// LOGO_PLACED on position: {pos}")
                
                placeholders.append({
                    "position": pos,
                    "images": images
                })

        # Build variants list
        variant_configs = [
            {"id": v["id"], "price": price_cents, "is_enabled": True}
            for v in variants
        ]

        # Build payload
        payload = {
            "title": f"[DRAFT]: {bp['title']}",
            "description": bp.get("description", ""),
            "blueprint_id": blueprint_id,
            "print_provider_id": provider_id,
            "variants": variant_configs,
            "print_areas": [
                {
                    "variant_ids": [v["id"] for v in variants],
                    "placeholders": placeholders,
                    "background": "#000000"
                }
            ]
        }

        print(f"// CREATING_PRODUCT with {len(placeholders)} placeholders...")

        resp = requests.post(
            f"{self.BASE_URL}/shops/{self.shop_id}/products.json",
            json=payload,
            headers=self.headers
        )

        if resp.status_code != 200:
            print(f"!! [SYSTEM_FAILURE]: {resp.text}")
            resp.raise_for_status()

        product = resp.json()
        print(f"--- [TEMPLATE_CREATED]: {product['id']} ---")
        print(f"Title: {product['title']}")
        print(f"Conduit: https://printify.com/app/store/{self.shop_id}/products/{product['id']}")

        return product


def main():
    parser = argparse.ArgumentParser(description="Printify Blueprint Explorer")
    parser.add_argument("--list", action="store_true", help="List all AOP blueprints")
    parser.add_argument("--unused", action="store_true", help="List only UNUSED AOP blueprints")
    parser.add_argument("--inspect", type=int, help="Inspect a specific blueprint ID")
    parser.add_argument("--create", type=int, help="Create template from blueprint ID")
    parser.add_argument("--tile", type=str, help="Path to tile image for template creation")
    parser.add_argument("--texture", type=str, help="Path to texture image for template creation")
    parser.add_argument("--logo", type=str, help="Path to logo image for template creation")
    parser.add_argument("--provider", type=int, default=None, help="Print provider ID (auto-detects if not specified)")
    parser.add_argument("--price", type=int, default=4500, help="Price in cents (default: 4500)")

    args = parser.parse_args()

    explorer = BlueprintExplorer()

    if args.list:
        blueprints = explorer.list_aop_blueprints()
        print(f"Found {len(blueprints)} AOP blueprints:\n")
        for bp in blueprints:
            print(f"  [{bp['id']:>4}] {bp['title']}")
        return

    if args.unused:
        print("[SYSTEM_LOG]: Scanning shop for used blueprints...")
        used = explorer.get_used_blueprint_ids()
        blueprints = explorer.list_aop_blueprints()
        unused = [b for b in blueprints if b['id'] not in used]
        print(f"\nUNUSED AOP Blueprints ({len(unused)} available, {len(used)} in use):\n")
        for bp in unused:
            print(f"  [{bp['id']:>4}] {bp['title']}")
        return

    if args.inspect:
        info = explorer.inspect_blueprint(args.inspect)
        print(f"\n=== Blueprint {info['id']}: {info['title']} ===")
        print(f"Brand: {info['brand']}")
        print(f"Description: {info['description']}...")
        print(f"\nPrint Providers:")
        for p in info["providers"]:
            # Get actual positions from API for this provider
            api_positions = explorer.get_positions_from_api(args.inspect, p['id'])
            print(f"  [{p['id']}] {p['title']} ({p['variant_count']} variants)")
            print(f"       Positions: {api_positions}")
            for v in p["sample_variants"]:
                print(f"       - {v.get('title', v.get('id'))}")
        return

    if args.create:
        product = explorer.create_template(
            blueprint_id=args.create,
            tile_path=args.tile,
            texture_path=args.texture,
            logo_path=args.logo,
            provider_id=args.provider,
            price_cents=args.price
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
