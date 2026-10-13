#!/usr/bin/env python3
"""
/* [FILE_ID]: MAP_BATCH_TO_TEMPLATE // VERSION: 1.0 // STATUS: STABLE */
Generic multi-frame garment mapping pipeline for collaborative specimen prototyping.

Features:
- Generic & reusable: operates on any folder of frames + optional logo.
- Auto-discovers garment schematics from existing [TEMPLATE] products in Printify.
- Multi-frame layout: distributes episodic frames across garment panels (front diptych/hero,
  pocket, back, sleeves, hood) with auto-scaling and positioning in JSON.
- Resolution-independent: coordinates and scales are normalized, ensuring lower-res
  screengrabs and future high-res 4K masters map identically.
- Non-invasive: operates in an isolated lane; never publishes to live channels by default.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
from dotenv import load_dotenv

# Ensure .env is loaded before importing Fabricator
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.skills.fabricator.fabricator import Fabricator

ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "collab"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def find_matching_template(fab: Fabricator, garment_query: str = "hoodie", template_id: Optional[str] = None) -> Optional[Dict]:
    """Finds a [TEMPLATE] product in Printify matching the garment keyword or returns by direct ID."""
    if template_id:
        try:
            return fab.get_product(template_id)
        except Exception as e:
            logging.warning("Could not fetch template by direct ID %s: %s", template_id, e)

    query = garment_query.lower()
    page = 1
    import requests
    while True:
        url = f"{fab.BASE_URL}/shops/{fab.shop_id}/products.json?page={page}"
        try:
            res = requests.get(url, headers=fab.headers, timeout=20)
            res.raise_for_status()
            data = res.json()
            products = data.get("data", [])
            if not products:
                break
            for p in products:
                title = p.get("title", "")
                if title.startswith("[TEMPLATE]:") and query in title.lower():
                    return p
            if data.get("current_page", page) >= data.get("last_page", page):
                break
            page += 1
        except Exception as e:
            logging.warning("Error fetching templates page %d: %s", page, e)
            break
    return None


def get_image_info(path: Path) -> Tuple[int, int, float]:
    """Returns (width, height, aspect_ratio = width / height)."""
    with Image.open(path) as img:
        w, h = img.size
        return w, h, (w / h if h else 1.0)


def build_multi_frame_placeholders(
    template_placeholders: List[Dict],
    uploaded_frames: List[Dict],
    uploaded_logo: Optional[Dict] = None,
    background_hex: str = "#000000"
) -> List[Dict]:
    """
    Constructs multi-frame placeholder assignments for an AOP garment.

    Layout strategy:
    - front: diptych (2 frames side-by-side) or hero frame, plus chest logo overlay
    - pocket: distinct episodic frame centered
    - back: diptych or hero cinematic frame
    - left_sleeve: vertical frame centered
    - right_sleeve: vertical frame centered
    - left_hood / right_hood: frame accent
    - trim / waistband / cuffs: solid black or accent, no unneeded clutter
    """
    num_frames = len(uploaded_frames)
    if num_frames == 0:
        raise ValueError("At least one frame image is required.")

    # Cycle frames deterministically
    def frame_at(idx: int) -> Dict:
        return uploaded_frames[idx % num_frames]

    out_placeholders = []

    # Map of positions to custom image layouts
    for ph in template_placeholders:
        pos = ph.get("position", "").lower()
        if not pos or pos == "all":
            # Skip empty meta-placeholders
            continue

        images: List[Dict] = []

        if pos == "front":
            if num_frames >= 2:
                # High-fashion diptych: two vertical frames side-by-side
                # Frame A (left chest/torso)
                images.append({
                    "id": frame_at(0)["id"],
                    "x": 0.28,
                    "y": 0.45,
                    "scale": 0.52,
                    "angle": 0
                })
                # Frame B (right chest/torso)
                images.append({
                    "id": frame_at(1)["id"],
                    "x": 0.72,
                    "y": 0.45,
                    "scale": 0.52,
                    "angle": 0
                })
            else:
                # Hero frame centered
                images.append({
                    "id": frame_at(0)["id"],
                    "x": 0.5,
                    "y": 0.45,
                    "scale": 0.95,
                    "angle": 0
                })

            # Overlay collab logo on upper chest if provided
            if uploaded_logo:
                images.append({
                    "id": uploaded_logo["id"],
                    "x": 0.72,
                    "y": 0.18,
                    "scale": 0.15,
                    "angle": 0
                })

        elif pos == "pocket":
            # Kangaroo pocket gets a featured narrative frame
            images.append({
                "id": frame_at(2)["id"],
                "x": 0.5,
                "y": 0.5,
                "scale": 0.95,
                "angle": 0
            })

        elif pos == "back":
            if num_frames >= 5:
                # Diptych on back for rich episodic storytelling
                images.append({
                    "id": frame_at(3)["id"],
                    "x": 0.28,
                    "y": 0.45,
                    "scale": 0.52,
                    "angle": 0
                })
                images.append({
                    "id": frame_at(4)["id"],
                    "x": 0.72,
                    "y": 0.45,
                    "scale": 0.52,
                    "angle": 0
                })
            else:
                images.append({
                    "id": frame_at(3 % num_frames)["id"],
                    "x": 0.5,
                    "y": 0.45,
                    "scale": 0.95,
                    "angle": 0
                })

        elif pos == "left_sleeve":
            images.append({
                "id": frame_at(5)["id"],
                "x": 0.5,
                "y": 0.5,
                "scale": 0.95,
                "angle": 0
            })

        elif pos == "right_sleeve":
            images.append({
                "id": frame_at(6)["id"],
                "x": 0.5,
                "y": 0.5,
                "scale": 0.95,
                "angle": 0
            })

        elif pos in ("left_hood", "right_hood"):
            images.append({
                "id": frame_at(0)["id"],
                "x": 0.5,
                "y": 0.5,
                "scale": 0.95,
                "angle": 0
            })

        elif pos in ("left_hood_lining", "right_hood_lining"):
            # Sleek lining or subtle accent
            images.append({
                "id": frame_at(1)["id"],
                "x": 0.5,
                "y": 0.5,
                "scale": 0.95,
                "angle": 0
            })

        elif "waistband" in pos or "cuff" in pos or "trim" in pos or "collar" in pos:
            # Preserve existing trim or use clean background
            # If template had trim images, preserve the base pattern with clean fields
            orig_imgs = ph.get("images", [])
            for orig in orig_imgs:
                clean_img = {
                    "id": orig.get("id"),
                    "x": orig.get("x", 0.5),
                    "y": orig.get("y", 0.5),
                    "scale": orig.get("scale", 1.0),
                    "angle": orig.get("angle", 0)
                }
                if "pattern" in orig:
                    clean_img["pattern"] = orig["pattern"]
                if "height" in orig:
                    clean_img["height"] = orig["height"]
                if "width" in orig:
                    clean_img["width"] = orig["width"]
                images.append(clean_img)

        # Only append placeholder if images exist
        if images:
            out_placeholders.append({
                "position": pos,
                "images": images
            })

    return out_placeholders


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic multi-frame garment mapper (Printify prototype lane)")
    parser.add_argument("--frames-dir", default="/home/cbg/Pictures/tcl/episode_1", help="Folder of input frame images")
    parser.add_argument("--logo", default="/home/cbg/Pictures/tcl/logo/20261012_11h44m21s_grim.png", help="Path to collab logo")
    parser.add_argument("--garment", default="hoodie", help="Keyword to search in [TEMPLATE] products (e.g. hoodie, tee, dress)")
    parser.add_argument("--template-id", default="69a928efcc7deb58a305b23f", help="Direct Printify product ID of the template (default: Men's Hoodie AOP)")
    parser.add_argument("--title", default=None, help="Custom draft title (default: [DRAFT]: Generic Collab Specimen)")
    parser.add_argument("--create-draft", action="store_true", help="Submit draft product to Printify (unlisted draft)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # 1. Initialize Fabricator (reads PRINTIFY_SHOP_ID and token from environment/.env)
    fab = Fabricator()
    logging.info("// HANDSHAKE_INITIALIZED: Shop ID %s", fab.shop_id)

    # 2. Locate garment template
    logging.info("// SCANNING_SCHEMATICS for [TEMPLATE]: *%s*...", args.garment)
    template = find_matching_template(fab, args.garment, template_id=args.template_id)
    if not template:
        logging.error("!! [SCHEMA_MISSING]: No [TEMPLATE] found matching '%s'", args.garment)
        return 2

    logging.info("// TEMPLATE_IDENTIFIED: '%s' (ID: %s, Blueprint: %s)", template["title"], template["id"], template.get("blueprint_id"))

    # 3. Load frames and logo
    frames_dir = Path(args.frames_dir)
    if not frames_dir.exists():
        logging.error("!! [ASSET_VOID]: Frames directory %s not found", frames_dir)
        return 3

    frame_files = sorted([p for p in frames_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
    if not frame_files:
        logging.error("!! [ASSET_VOID]: No images found in %s", frames_dir)
        return 4

    logging.info("// INGESTED_FRAMES: %d assets from %s", len(frame_files), frames_dir.name)

    logo_path = Path(args.logo) if args.logo else None
    if logo_path and not logo_path.exists():
        logging.warning("!! [LOGO_NOT_FOUND]: %s not found, proceeding without logo overlay", logo_path)
        logo_path = None

    # 4. Upload assets to Printify Media Library
    logging.info("// SECURING_MEDIA_ARTIFACTS on Printify CDN...")
    uploaded_frames = []
    for f in frame_files:
        w, h, ar = get_image_info(f)
        img_id = fab.upload_image(local_path=str(f), file_name=f"collab_frame_{f.name}")
        uploaded_frames.append({
            "path": str(f),
            "id": img_id,
            "width": w,
            "height": h,
            "aspect_ratio": ar
        })

    uploaded_logo = None
    if logo_path:
        w, h, ar = get_image_info(logo_path)
        logo_id = fab.upload_image(local_path=str(logo_path), file_name=f"collab_logo_{logo_path.name}")
        uploaded_logo = {
            "path": str(logo_path),
            "id": logo_id,
            "width": w,
            "height": h,
            "aspect_ratio": ar
        }

    # 5. Build Printify Schematic Payload
    source_product = fab.get_product(template["id"])
    print_areas = source_product.get("print_areas", [])
    new_print_areas = []

    for area in print_areas:
        orig_placeholders = area.get("placeholders", [])
        mapped_placeholders = build_multi_frame_placeholders(
            orig_placeholders,
            uploaded_frames,
            uploaded_logo,
            background_hex="#000000"
        )
        new_print_areas.append({
            "variant_ids": area.get("variant_ids"),
            "placeholders": mapped_placeholders,
            "background": "#000000"
        })

    # Preserve enabled variants
    variants = []
    for v in source_product.get("variants", []):
        if v.get("is_enabled", True):
            variants.append({
                "id": v["id"],
                "price": v.get("price"),
                "is_enabled": True
            })

    title = args.title or f"[DRAFT]: Specimen Prototype - {template.get('title', '').replace('[TEMPLATE]:', '').strip()}"

    payload = {
        "title": title,
        "description": "Prototype collaboration specimen. Multi-frame episodic arrangement. Strictly draft status.",
        "blueprint_id": source_product.get("blueprint_id"),
        "print_provider_id": source_product.get("print_provider_id"),
        "variants": variants,
        "print_areas": new_print_areas,
        "tags": ["CBG Studio", "specimen-prototype", "draft"]
    }

    # 6. Save Draft Payload to Artifacts
    output_path = ARTIFACTS_DIR / f"{Path(args.frames_dir).name}-draft-schematic.json"
    output_path.write_text(json.dumps(payload, indent=2))
    logging.info("// DRAFT_SCHEMATIC_SAVED: %s", output_path)

    # 7. Optionally submit draft product to Printify
    if args.create_draft:
        import requests
        logging.info("// TRANSMITTING_SCHEMATIC to Printify...")
        url = f"{Fabricator.BASE_URL}/shops/{fab.shop_id}/products.json"
        res = requests.post(url, json=payload, headers=fab.headers)
        try:
            res.raise_for_status()
            prod_data = res.json()
            logging.info("// DRAFT_PRODUCT_REALIZED: Product ID %s", prod_data.get("id"))
            logging.info("Inspect preview at: https://printify.com/app/store/products/%s", prod_data.get("id"))
        except requests.HTTPError as e:
            logging.error("!! [INJECTION_FAILURE]: %s - %s", e, res.text)
            return 5
    else:
        logging.info("// DRY_RUN_COMPLETE: Draft schematic prepared. Pass --create-draft to materialize as a draft in Printify.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
