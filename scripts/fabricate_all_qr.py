#!/usr/bin/env python3
# [FILE_ID]: scripts/FABRICATE_ALL_QR // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: ONE-OFF_BATCH_PROTOCOL // QR_LOGO_SWAP_ONLY
"""
Batch fabrication: Iterates ALL templates, keeps existing graphics (tiles/textures),
swaps ONLY the logo role for the Repository Portal QR code.
Generates products, lifestyle mockups, and blog posts for each.

Usage:
    source .venv/bin/activate
    python3 scripts/fabricate_all_qr.py
"""

import sys
import os
import time
import json
import requests
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from dotenv import load_dotenv
from agents.skills.fabricator.fabricator import Fabricator
from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image

load_dotenv()

QR_LOGO_PATH = Path("artifacts/graphics/logos/repo_portal_qr.png")
STAMP_PATH = QR_LOGO_PATH  # Same QR used as stamp


def apply_unverified_stamp(image_path: str) -> str:
    """Composites the STATUS: UNVERIFIED stamp onto the image."""
    if not STAMP_PATH.exists():
        print(f"!! [WARNING]: Stamp not found at {STAMP_PATH}. Skipping.")
        return image_path

    try:
        base_img = Image.open(image_path).convert("RGBA")
        stamp = Image.open(str(STAMP_PATH)).convert("RGBA")

        stamp_size = max(int(base_img.width * 0.12), 48)
        stamp = stamp.resize((stamp_size, stamp_size), Image.LANCZOS)

        padding = int(base_img.width * 0.03)
        x = base_img.width - stamp_size - padding
        y = base_img.height - stamp_size - padding

        base_img.paste(stamp, (x, y), stamp)
        base_img.save(image_path)
        print(f"// STAMP_APPLIED: STATUS: UNVERIFIED @ ({x}, {y})")
        return image_path
    except Exception as e:
        print(f"!! [WARNING]: Stamp application failed: {e}")
        return image_path


def synthesize_lifestyle_mockup(product_title: str, mockup_url: str) -> str:
    """Synthesizes a lifestyle image using the Printify mockup as context."""
    print(f"[SIGNAL_BROADCAST]: Synthesizing Lifestyle Mockup for {product_title}...")

    image_context = None
    try:
        resp = requests.get(mockup_url)
        resp.raise_for_status()
        image_context = Image.open(io.BytesIO(resp.content))
        print(f"✅ [SYSTEM_LOG]: Mockup context secured.")
    except Exception as e:
        print(f"⚠️ [SYSTEM_WARNING]: Failed to fetch mockup: {e}")

    prompt = (
        f"CBG Studio | Lifestyle Realization: A high-fidelity lifestyle photo. "
        f"The subject is the specific apparel product shown in the provided image. "
        f"CRITICAL: The product in the new photo must be EXACTLY identical to the base image. "
        f"Replicate the pattern, colors, and placement with 100% precision. "
        f"Context: QR Portal Edition. Visual Reference: industrial noir techwear aesthetic, "
        f"high-contrast shadows, clinical warehouse lighting. Medium close-up shot."
    )

    output_path = generate_nano_banana_image(
        prompt,
        graphic_type_override="mockups",
        image_context=image_context
    )
    return output_path


def fabricate_qr_swap(fab: Fabricator, template_id: str) -> dict:
    """
    Clones template, keeps ALL existing images EXCEPT logo role which is replaced with QR.
    """
    print(f"\n--- [QR_SWAP_FABRICATION]: TEMPLATE_{template_id} ---")

    # 1. Get Source
    source = fab.get_product(template_id)
    source_title = source.get('title', '').replace('[TEMPLATE]: ', '').strip()
    print(f"// SOURCE_TEMPLATE: {source_title}")

    # 2. Analyze image roles
    image_roles = {}  # original_id -> role
    for area in source.get('print_areas', []):
        for ph in area.get('placeholders', []):
            pos = ph.get('position', '').lower()
            is_trim_area = any(x in pos for x in ['waistband', 'trim', 'collar', 'cuff'])
            for img in ph.get('images', []):
                img_id = img['id']
                if img_id in image_roles:
                    continue
                if 'pattern' in img:
                    image_roles[img_id] = 'tile'
                elif is_trim_area:
                    image_roles[img_id] = 'texture'
                elif img.get('scale', 1) < 0.4:
                    image_roles[img_id] = 'logo'
                else:
                    image_roles[img_id] = 'texture'

    print(f"// IDENTIFIED_ROLES: {image_roles}")

    # 3. Upload QR logo ONCE if there's a logo role
    logo_ids = [oid for oid, role in image_roles.items() if role == 'logo']
    qr_new_id = None

    if logo_ids:
        if not QR_LOGO_PATH.exists():
            print(f"!! [FAILURE]: QR logo not found at {QR_LOGO_PATH}")
            return None
        print(f"// UPLOADING_QR_LOGO: {QR_LOGO_PATH.name}")
        qr_new_id = fab.upload_image(
            local_path=str(QR_LOGO_PATH),
            file_name=f"qr_portal_{template_id}.png"
        )

    # 4. Build new print_areas: keep all images except swap logos
    new_print_areas = []
    for area in source.get('print_areas', []):
        new_placeholders = []
        for placeholder in area.get('placeholders', []):
            new_images_list = []
            for img in placeholder.get('images', []):
                img_id = img.get('id')
                role = image_roles.get(img_id)

                if role == 'logo' and qr_new_id:
                    # Swap logo for QR
                    new_img = {
                        "id": qr_new_id,
                        "x": img.get('x', 0.5),
                        "y": img.get('y', 0.5),
                        "scale": img.get('scale', 1),
                        "angle": img.get('angle', 0),
                    }
                    if 'height' in img:
                        new_img['height'] = img['height']
                    if 'width' in img:
                        new_img['width'] = img['width']
                    new_images_list.append(new_img)
                    print(f"// SWAPPED_LOGO: {img_id} -> {qr_new_id}")
                else:
                    # Keep original image reference
                    new_images_list.append(img)

            if new_images_list:
                new_placeholders.append({
                    "position": placeholder.get('position'),
                    "images": new_images_list
                })

        if new_placeholders:
            new_print_areas.append({
                "variant_ids": area.get('variant_ids'),
                "placeholders": new_placeholders,
                "background": area.get('background')
            })

    # 5. Build variants
    variants = [
        {"id": v['id'], "price": v['price'], "is_enabled": True}
        for v in source.get('variants', [])
        if v.get('is_enabled', True)
    ]

    # 6. Payload - Use placeholder, will update after creation with product ID
    payload = {
        "title": "UNVERIFIED SPECIMEN",
        "description": "",
        "blueprint_id": source.get('blueprint_id'),
        "print_provider_id": source.get('print_provider_id'),
        "variants": variants,
        "print_areas": new_print_areas
    }

    # 7. Create product
    print("// INJECTING_SCHEMATIC...")
    create_url = f"{fab.BASE_URL}/shops/{fab.shop_id}/products.json"
    response = requests.post(create_url, json=payload, headers=fab.headers)

    if response.status_code != 200:
        print(f"!! [SYSTEM_FAILURE]: {response.text}")
        response.raise_for_status()

    product = response.json()
    product_id = product['id']

    # Update title with product ID per protocol (description = source prompts only)
    specimen_title = f"UNVERIFIED SPECIMEN: {product_id}"
    specimen_description = source.get('description', '')
    fab.update_product(product_id, {"title": specimen_title, "description": specimen_description})
    product['title'] = specimen_title
    product['description'] = specimen_description
    print(f"// SPECIMEN_TAGGED: {specimen_title}")
    print(f"--- [FABRICATION_COMPLETE]: {specimen_title} ---")

    return product


def process_template(fab: Fabricator, template: dict) -> bool:
    """Full pipeline for one template: product + mockup + blog."""
    template_id = template['id']
    template_title = template.get('title', '')
    print(f"\n{'='*60}")
    print(f"[BATCH_PROCESS]: {template_title}")
    print(f"{'='*60}")

    try:
        # 1. Fabricate product with QR swap
        product = fabricate_qr_swap(fab, template_id)
        if not product:
            print(f"❌ [SYSTEM_ERROR]: Fabrication failed for {template_title}")
            return False

        product_id = product['id']
        product_title = product.get('title', '')

        # 2. Wait for Printify to generate mockups
        print("[SYSTEM_LOG]: Waiting for mockup generation...")
        time.sleep(6)

        # 3. Re-fetch product for mockup URLs
        product = fab.get_product(product_id)
        images = product.get('images', [])

        if not images:
            print(f"⚠️ [WARNING]: No mockup images for {product_id}. Skipping lifestyle.")
            return True

        # Find front mockup
        mockup_url = images[0].get('src')
        for img in images:
            if 'front' in img.get('src', '').lower():
                mockup_url = img.get('src')
                break

        # 4. Synthesize lifestyle mockup
        lifestyle_path = synthesize_lifestyle_mockup(product_title, mockup_url)

        if lifestyle_path and os.path.exists(lifestyle_path):
            # Apply stamp
            apply_unverified_stamp(lifestyle_path)

            # Upload lifestyle image
            file_size = os.path.getsize(lifestyle_path)
            print(f"// UPLOADING_LIFESTYLE: {lifestyle_path} ({file_size} bytes)")

            lifestyle_media_id = fab.upload_image(
                local_path=lifestyle_path,
                file_name=f"lifestyle_qr_{product_id}.png"
            )
            lifestyle_src_url = fab.last_upload_src

            if lifestyle_media_id:
                print(f"// ARTIFACT_SECURED: ID_{lifestyle_media_id}")
                print(f"// LIFESTYLE_CDN: {lifestyle_src_url}")

                # Archive linkage
                mapping_file = Path(lifestyle_path).parent / "product_link.json"
                link_data = {
                    "product_id": product_id,
                    "product_title": product_title,
                    "conduit_url": f"https://printify.com/app/store/{fab.shop_id}/products/{product_id}",
                    "lifestyle_media_id": lifestyle_media_id,
                    "lifestyle_src_url": lifestyle_src_url,
                    "lifestyle_local_path": lifestyle_path,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                mapping_file.write_text(json.dumps(link_data, indent=4))
                print(f"✅ [SYSTEM_LOG]: Linkage secured: {mapping_file}")

                # Rename folder with product ID
                old_folder = Path(lifestyle_path).parent
                new_folder_name = f"{old_folder.name}__{product_id}"
                new_folder = old_folder.parent / new_folder_name
                try:
                    old_folder.rename(new_folder)
                    print(f"// FOLDER_RENAMED: {new_folder_name}")
                except Exception as rename_err:
                    print(f"!! [WARNING]: Folder rename failed: {rename_err}")
                    new_folder = old_folder

                # 5. Post blog entry - no prompts in QR swap, just footer
                fab.post_blog_for_product(
                    product_id=product_id,
                    title=product_title,
                    description="",
                    mockups_dir=str(new_folder.parent)
                )

        print(f"✅ [TEMPLATE_COMPLETE]: {product_title}")
        print(f"   CONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product_id}")
        return True

    except Exception as e:
        print(f"❌ [SYSTEM_ERROR]: Failed processing {template_title}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("[SYSTEM_LOG]: ═══ BATCH QR PORTAL FABRICATION ═══")
    print("[SYSTEM_LOG]: Swapping logos for QR code on ALL templates.\n")

    fab = Fabricator()
    templates = fab.get_templates()

    if not templates:
        print("[SYSTEM_ERROR]: No templates found. Ensure products are titled '[TEMPLATE]: ...'")
        sys.exit(1)

    print(f"[SYSTEM_LOG]: Found {len(templates)} template(s):")
    for t in templates:
        print(f"  - {t['title']} (ID: {t['id']})")

    print()
    success_count = 0
    fail_count = 0

    for template in templates:
        if process_template(fab, template):
            success_count += 1
        else:
            fail_count += 1

        # Brief pause between templates to avoid API rate limits
        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"[BATCH_COMPLETE]: {success_count} succeeded, {fail_count} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
