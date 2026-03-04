#!/usr/bin/env python3
"""
/* [FILE_ID]: TRANSPOSE_SPECIMEN // VERSION: 1.0 // STATUS: STABLE */
Transpose an existing product's images onto a new template.

This script extracts images from a source product, applies them to a different 
template, and runs the full pipeline (lifestyle mockup + blog post).

Usage:
    # Specific source + random template
    python3 scripts/transpose_specimen.py --source 69a7a890c946b046a702713a

    # Specific source + specific template
    python3 scripts/transpose_specimen.py --source 69a7a890c946b046a702713a --template Hoodie

    # Random source + specific template
    python3 scripts/transpose_specimen.py --random-source --template "Sweatshirt"

    # Random source + random template
    python3 scripts/transpose_specimen.py --random-source

    # Dry run (show what would happen)
    python3 scripts/transpose_specimen.py --source 69a7a890c946b046a702713a --dry-run
"""

import sys
import os
import argparse
import random
import time
import json
import re
import requests
import io
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.skills.fabricator.fabricator import Fabricator

# Lazy import to avoid heavy deps on --help
def get_shopify_conduit():
    import importlib.util
    skill_path = Path(__file__).parent.parent / "agents" / "skills" / "shopify_skill" / "shopify_skill.py"
    spec = importlib.util.spec_from_file_location("shopify_skill", skill_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ShopifyConduit()

STAMP_PATH = Path("artifacts/graphics/logos/repo_portal_qr.png")
TEMPLATE_HISTORY_PATH = Path("artifacts/.last_template_id")
TRANSPOSE_CACHE_DIR = Path("artifacts/graphics/.transpose_cache")
UNVERIFIED_BLOG_TITLE = "[STATUS: UNVERIFIED]"


def extract_product_images(fab: Fabricator, product_id: str) -> dict:
    """
    Extract images from a product and map them to roles.
    Returns dict: {role: {'id': image_id, 'src': url, ...}}
    """
    product = fab.get_product(product_id)
    title = product.get('title', 'Unknown')
    print(f"// SOURCE_PRODUCT: {title} (ID: {product_id})")
    
    image_data = {}  # role -> image info
    image_frequency = {}  # id -> count (to identify main body image)
    
    # First pass: count image frequencies to identify main body (tile)
    for area in product.get('print_areas', []):
        for ph in area.get('placeholders', []):
            for img in ph.get('images', []):
                img_id = img['id']
                image_frequency[img_id] = image_frequency.get(img_id, 0) + 1
    
    # Identify the most frequent image as tile (main body)
    tile_id = max(image_frequency, key=image_frequency.get) if image_frequency else None
    
    # Second pass: map images to roles
    for area in product.get('print_areas', []):
        for ph in area.get('placeholders', []):
            pos = ph.get('position', '').lower()
            is_trim = any(x in pos for x in ['waistband', 'trim', 'collar', 'cuff', 'sleeve'])
            
            for img in ph.get('images', []):
                img_id = img['id']
                
                if img_id in [v.get('id') for v in image_data.values()]:
                    continue
                
                # Determine role
                if img_id == tile_id:
                    role = 'tile'
                elif img.get('scale', 1) < 0.4:
                    role = 'logo'
                elif is_trim or 'pattern' not in img:
                    role = 'texture'
                else:
                    role = 'texture'
                
                image_data[role] = {
                    'id': img_id,
                    'x': img.get('x', 0.5),
                    'y': img.get('y', 0.5),
                    'scale': img.get('scale', 1),
                    'angle': img.get('angle', 0),
                    'pattern': img.get('pattern'),
                    'src': img.get('src', '')
                }
    
    print(f"// EXTRACTED_ROLES: {list(image_data.keys())}")
    for role, data in image_data.items():
        print(f"   [{role}] ID: {data['id']}")
    
    return image_data


def download_image_to_cache(image_id: str, src_url: str) -> str:
    """
    Download an image from Printify CDN to local cache.
    Returns local path.
    """
    TRANSPOSE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = TRANSPOSE_CACHE_DIR / f"{image_id}.png"
    
    if local_path.exists():
        print(f"// CACHE_HIT: {local_path}")
        return str(local_path)
    
    print(f"// DOWNLOADING: {image_id}...")
    try:
        resp = requests.get(src_url, timeout=30)
        resp.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(resp.content)
        print(f"// CACHED: {local_path}")
        return str(local_path)
    except Exception as e:
        print(f"!! [WARNING]: Download failed for {image_id}: {e}")
        return None


def find_blog_article_for_product(product_id: str) -> dict:
    """
    Search Shopify blog for an article about this product.
    Returns article dict or None.
    """
    try:
        conduit = get_shopify_conduit()
        blogs = conduit.list_blogs()
        
        blog_id = None
        for b in blogs:
            if b.get('title', '').strip() == UNVERIFIED_BLOG_TITLE:
                blog_id = b['id']
                break
        
        if not blog_id:
            print(f"// BLOG_NOT_FOUND: {UNVERIFIED_BLOG_TITLE}")
            return None
        
        articles = conduit.list_articles(blog_id, limit=250)
        
        for article in articles:
            title = article.get('title', '')
            # Match pattern: "UNVERIFIED SPECIMEN: <product_id>"
            if product_id in title:
                full_article = conduit.get_article(blog_id, article['id'])
                print(f"// ARTICLE_FOUND: {title}")
                return full_article
        
        print(f"// NO_ARTICLE: No blog entry found for product {product_id}")
        return None
    except Exception as e:
        print(f"!! [WARNING]: Blog search failed: {e}")
        return None


def extract_description_from_article(article: dict) -> str:
    """
    Extract the description/content from a blog article.
    Strips footer sections and HTML tags for clean text.
    """
    if not article:
        return ""
    
    body = article.get('body_html', '')
    
    # Strip the footer section if present
    footer_marker = "[NOTICE: EXTERNAL_LAB_ANALYSIS_REQUIRED]"
    if footer_marker in body:
        body = body.split(footer_marker)[0]
    
    # Basic HTML stripping
    body = re.sub(r'<[^>]+>', ' ', body)
    body = re.sub(r'\s+', ' ', body).strip()
    
    return body


def apply_unverified_stamp(image_path: str) -> str:
    """Apply STATUS: UNVERIFIED stamp to bottom-right corner."""
    if not STAMP_PATH.exists():
        print(f"!! [WARNING]: Stamp not found. Skipping.")
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
        print(f"// STAMP_APPLIED: ({x}, {y})")
        return image_path
    except Exception as e:
        print(f"!! [WARNING]: Stamp failed: {e}")
        return image_path


def synthesize_lifestyle_mockup(theme_desc: str, product_title: str, mockup_url: str):
    """Generate lifestyle mockup using Nanobanana."""
    from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image
    
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
        f"CRITICAL: The product pattern must be EXACTLY identical to the base image. "
        f"Context: {theme_desc}. "
        f"Visual Reference Style: industrial noir techwear aesthetic, high-contrast shadows, clinical warehouse lighting. "
        f"Medium close-up, focusing on the quality and design of the product specimen."
    )
    
    output_path = generate_nano_banana_image(
        prompt,
        graphic_type_override="mockups",
        image_context=image_context
    )
    return output_path


def transpose_specimen(
    source_product_id: str,
    template_search: str = None,
    template_id: str = None,
    dry_run: bool = False
):
    """
    Main transposition logic: extract images from source, apply to template.
    """
    load_dotenv()
    fab = Fabricator()
    
    print(f"\n{'='*60}")
    print(f"[TRANSPOSE_PROTOCOL]: INITIATING")
    print(f"{'='*60}\n")
    
    # 1. Extract images from source product
    print("[PHASE_1]: EXTRACTING SOURCE IMAGES")
    source_images = extract_product_images(fab, source_product_id)
    
    if not source_images:
        print("[SYSTEM_ERROR]: No images found in source product.")
        return None
    
    # 2. Get description from Shopify blog (if available)
    print("\n[PHASE_2]: SCANNING BLOG ARCHIVES")
    article = find_blog_article_for_product(source_product_id)
    description = extract_description_from_article(article)
    if description:
        print(f"// DESCRIPTION_EXTRACTED: {description[:100]}...")
    
    # 3. Select target template
    print("\n[PHASE_3]: SELECTING TARGET TEMPLATE")
    
    last_template_id = None
    if TEMPLATE_HISTORY_PATH.exists():
        last_template_id = TEMPLATE_HISTORY_PATH.read_text().strip()
    
    if template_id:
        # Direct product ID provided - use it as template even if not marked as [TEMPLATE]
        try:
            template = fab.get_product(template_id)
            print(f"// USING_PRODUCT_AS_TEMPLATE: {template.get('title')} (ID: {template_id})")
        except Exception as e:
            print(f"[ERROR]: Could not fetch product {template_id}: {e}")
            return None
    elif template_search:
        templates = fab.get_templates()
        matches = [t for t in templates if template_search.lower() in t['title'].lower()]
        if not matches:
            print(f"[WARNING]: No template matching '{template_search}'. Selecting random.")
            matches = templates
        filtered = [t for t in matches if t['id'] != last_template_id]
        template = random.choice(filtered if filtered else matches)
    else:
        templates = fab.get_templates()
        filtered = [t for t in templates if t['id'] != last_template_id]
        template = random.choice(filtered if filtered else templates)
    
    # Don't transpose onto the same product's template (skip if explicit template_id was provided)
    source_product = fab.get_product(source_product_id)
    source_blueprint = source_product.get('blueprint_id')
    template_blueprint = template.get('blueprint_id')
    
    if source_blueprint == template_blueprint and not template_id:
        print(f"[WARNING]: Source and template use same blueprint. Selecting different template.")
        alternatives = [t for t in templates if t.get('blueprint_id') != source_blueprint and t['id'] != last_template_id]
        if alternatives:
            template = random.choice(alternatives)
        else:
            print(f"[WARNING]: No alternative blueprints available.")
    elif source_blueprint == template_blueprint:
        print(f"[NOTICE]: Source and template use same blueprint (explicit selection honored).")
    
    print(f"// TARGET_TEMPLATE: {template['title']} (ID: {template['id']})")
    
    # Persist selection
    try:
        TEMPLATE_HISTORY_PATH.write_text(template['id'])
    except Exception:
        pass
    
    if dry_run:
        print("\n[DRY_RUN]: Would transpose:")
        print(f"  Source: {source_product_id}")
        print(f"  Template: {template['title']}")
        print(f"  Roles: {list(source_images.keys())}")
        return None
    
    # 4. Prepare role overrides - we'll re-use the image IDs directly
    print("\n[PHASE_4]: PREPARING FABRICATION PAYLOAD")
    
    # For transpose, we use the existing Printify image IDs instead of uploading new images
    # This requires modifying the fabricator call or directly constructing the payload
    role_to_image_id = {}
    for role, img_data in source_images.items():
        role_to_image_id[role] = img_data['id']
        print(f"// MAPPING: {role} -> {img_data['id']}")
    
    # 5. Construct and submit product
    print("\n[PHASE_5]: FABRICATING NEW SPECIMEN")
    
    try:
        # We need to use a custom fabrication since we're reusing image IDs
        product = fabricate_with_existing_images(fab, template['id'], role_to_image_id, source_images)
        product_id = product.get('id')
        product_title = product.get('title')
        
        print(f"\n--- [FABRICATION_COMPLETE]: ID_{product_id} ---")
        print(f"SPECIMEN: {product_title}")
        
        # 6. Lifestyle realization
        print("\n[PHASE_6]: LIFESTYLE_REALIZATION")
        time.sleep(5)  # Let Printify initialize
        
        product = fab.get_product(product_id)
        images = product.get('images', [])
        
        if images:
            mockup_url = images[0].get('src')
            for img in images:
                if 'front' in str(img.get('variant_ids', [])).lower() or 'front' in img.get('src', '').lower():
                    mockup_url = img.get('src')
                    break
            
            theme_desc = description[:200] if description else "Industrial Noir Transposition"
            lifestyle_path = synthesize_lifestyle_mockup(theme_desc, product_title, mockup_url)
            
            if lifestyle_path:
                apply_unverified_stamp(lifestyle_path)
                print(f"[SYSTEM_LOG]: Lifestyle artifact stabilized.")
                
                if os.path.exists(lifestyle_path):
                    lifestyle_media_id = fab.upload_image(
                        local_path=lifestyle_path,
                        file_name=f"lifestyle_{product_id}.png"
                    )
                    lifestyle_src = fab.last_upload_src
                    
                    if lifestyle_media_id:
                        print(f"// ARTIFACT_SECURED: ID_{lifestyle_media_id}")
                        
                        # Archive linkage
                        mapping_file = Path(lifestyle_path).parent / "product_link.json"
                        link_data = {
                            "product_id": product_id,
                            "product_title": product_title,
                            "source_product_id": source_product_id,
                            "conduit_url": f"https://printify.com/app/store/{fab.shop_id}/products/{product_id}",
                            "lifestyle_media_id": lifestyle_media_id,
                            "lifestyle_src_url": lifestyle_src,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        }
                        mapping_file.write_text(json.dumps(link_data, indent=4))
                        print(f"✅ [SYSTEM_LOG]: Linkage secured: {mapping_file}")
                        
                        # Rename folder
                        old_folder = Path(lifestyle_path).parent
                        new_folder_name = f"{old_folder.name}__{product_id}"
                        new_folder = old_folder.parent / new_folder_name
                        try:
                            old_folder.rename(new_folder)
                            print(f"// FOLDER_RENAMED: {new_folder_name}")
                        except Exception as e:
                            print(f"!! [WARNING]: Folder rename failed: {e}")
                            new_folder = old_folder
                        
                        # Post to blog
                        fab.post_blog_for_product(
                            product_id=product_id,
                            title=product_title,
                            description=description or '',
                            mockups_dir=str(new_folder.parent)
                        )
        
        print(f"\nCONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product_id}")
        return product
        
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Transposition failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def fabricate_with_existing_images(fab: Fabricator, template_id: str, role_to_image_id: dict, source_images: dict) -> dict:
    """
    Clone template and inject existing Printify image IDs (no upload needed).
    """
    source = fab.get_product(template_id)
    
    # Analyze template structure
    template_image_roles = {}
    for area in source.get('print_areas', []):
        for ph in area.get('placeholders', []):
            pos = ph.get('position', '').lower()
            is_trim = any(x in pos for x in ['waistband', 'trim', 'collar', 'cuff'])
            
            for img in ph.get('images', []):
                img_id = img['id']
                if img_id in template_image_roles:
                    continue
                
                if 'pattern' in img:
                    template_image_roles[img_id] = 'tile'
                elif is_trim:
                    template_image_roles[img_id] = 'texture'
                elif img.get('scale', 1) < 0.4:
                    template_image_roles[img_id] = 'logo'
                else:
                    template_image_roles[img_id] = 'tile'
    
    print(f"// TEMPLATE_ROLES: {template_image_roles}")
    
    # Map template image IDs to source image IDs by role
    id_mapping = {}
    for template_img_id, role in template_image_roles.items():
        if role in role_to_image_id:
            id_mapping[template_img_id] = role_to_image_id[role]
    
    # Construct new print_areas
    new_print_areas = []
    for area in source.get('print_areas', []):
        new_placeholders = []
        for ph in area.get('placeholders', []):
            images = ph.get('images', [])
            if not images:
                continue
            
            new_images = []
            for img in images:
                original_id = img.get('id')
                replacement_id = id_mapping.get(original_id)
                role = template_image_roles.get(original_id, 'tile')
                
                if replacement_id:
                    # Use source image metadata for positioning
                    src_meta = source_images.get(role, {})
                    new_img = {
                        "id": replacement_id,
                        "x": img.get('x', 0.5),
                        "y": img.get('y', 0.5),
                        "scale": img.get('scale', 1),
                        "angle": img.get('angle', 0)
                    }
                    if 'pattern' in img:
                        new_img['pattern'] = img['pattern']
                    if 'height' in img:
                        new_img['height'] = img['height']
                    if 'width' in img:
                        new_img['width'] = img['width']
                    new_images.append(new_img)
                else:
                    new_images.append(img)
            
            new_placeholders.append({
                "position": ph.get('position'),
                "images": new_images
            })
        
        new_print_areas.append({
            "variant_ids": area.get('variant_ids', []),
            "placeholders": new_placeholders,
            "background": area.get('background', '#ffffff')
        })
    
    # Build payload
    payload = {
        "title": f"UNVERIFIED SPECIMEN: transposed_{int(time.time())}",
        "blueprint_id": source['blueprint_id'],
        "print_provider_id": source['print_provider_id'],
        "variants": source['variants'],
        "print_areas": new_print_areas
    }
    
    # Submit to Printify
    url = f"{fab.BASE_URL}/shops/{fab.shop_id}/products.json"
    response = requests.post(url, json=payload, headers=fab.headers)
    response.raise_for_status()
    product = response.json()
    
    # Rename to standard format
    new_title = f"UNVERIFIED SPECIMEN: {product['id']}"
    fab.update_product(product['id'], {"title": new_title})
    product['title'] = new_title
    print(f"// SPECIMEN_TAGGED: {new_title}")
    
    return product


def get_random_unverified_product(fab: Fabricator) -> str:
    """Select a random UNVERIFIED SPECIMEN product ID."""
    all_products = []
    page = 1
    
    while True:
        url = f"{fab.BASE_URL}/shops/{fab.shop_id}/products.json?page={page}"
        response = requests.get(url, headers=fab.headers)
        response.raise_for_status()
        data = response.json()
        products = data.get('data', [])
        
        if not products:
            break
        
        all_products.extend(products)
        
        if data.get('current_page', page) >= data.get('last_page', page):
            break
        page += 1
    
    # Filter to UNVERIFIED SPECIMENs (not templates)
    specimens = [
        p for p in all_products 
        if p.get('title', '').startswith('UNVERIFIED SPECIMEN:')
    ]
    
    if not specimens:
        raise ValueError("No UNVERIFIED SPECIMEN products found.")
    
    chosen = random.choice(specimens)
    print(f"// RANDOM_SOURCE: {chosen['title']} (ID: {chosen['id']})")
    return chosen['id']


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CBG Transpose Protocol — Clone images from one product to another template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Specific source, random template
  python3 scripts/transpose_specimen.py --source 69a7a890c946b046a702713a

  # Specific source, specific template
  python3 scripts/transpose_specimen.py --source 69a7a890c946b046a702713a --template Hoodie

  # Random source, specific template  
  python3 scripts/transpose_specimen.py --random-source --template "Sweatshirt (AOP)"

  # Fully random
  python3 scripts/transpose_specimen.py --random-source
        """
    )
    
    parser.add_argument("--source", type=str, help="Source product ID to extract images from")
    parser.add_argument("--random-source", action="store_true", help="Select a random UNVERIFIED SPECIMEN as source")
    parser.add_argument("--template", type=str, help="Template search string or ID")
    parser.add_argument("--template-id", type=str, help="Explicit template ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without executing")
    
    args = parser.parse_args()
    
    if not args.source and not args.random_source:
        parser.error("Either --source or --random-source is required")
    
    load_dotenv()
    fab = Fabricator()
    
    # Resolve source product
    if args.random_source:
        source_id = get_random_unverified_product(fab)
    else:
        source_id = args.source
    
    transpose_specimen(
        source_product_id=source_id,
        template_search=args.template,
        template_id=args.template_id,
        dry_run=args.dry_run
    )
