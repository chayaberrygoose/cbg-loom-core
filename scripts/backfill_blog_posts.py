#!/usr/bin/env python3
# [FILE_ID]: scripts/BACKFILL_BLOG_POSTS // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: AUDIT_AND_BACKFILL_MISSING_BLOG_POSTS

"""
Audits Printify products vs Shopify blog posts and backfills missing entries.

Usage:
    # Audit products since 5am today
    python scripts/backfill_blog_posts.py

    # Specify cutoff time
    python scripts/backfill_blog_posts.py --since "2026-03-05 05:00:00"

    # Dry run (show what would be created)
    python scripts/backfill_blog_posts.py --dry-run

    # Skip lifestyle generation (use Printify mockup instead)
    python scripts/backfill_blog_posts.py --skip-lifestyle
"""

import sys
import os
import argparse
import json
import time
import requests
import io
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agents.skills.fabricator.fabricator import Fabricator
from agents.skills.shopify_skill.shopify_skill import ShopifyConduit
from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}")


def get_all_printify_products(fab: Fabricator) -> list:
    """Retrieves all products from Printify (paginated)."""
    all_products = []
    page = 1
    
    while True:
        url = f"{fab.BASE_URL}/shops/{fab.shop_id}/products.json?page={page}"
        
        for attempt in range(3):
            response = requests.get(url, headers=fab.headers)
            if response.status_code >= 500:
                _log(f"!! [SIGNAL_WARPING]: {response.status_code} Error (page {page}). Retrying...")
                time.sleep(5)
                continue
            break
            
        response.raise_for_status()
        data = response.json()
        products = data.get('data', [])
        
        if not products:
            break
            
        all_products.extend(products)
        
        current_page = data.get('current_page', page)
        last_page = data.get('last_page', page)
        if current_page >= last_page:
            break
        
        page += 1
    
    return all_products


def parse_printify_timestamp(ts_str: str) -> datetime:
    """Parse Printify timestamp format."""
    # Format: "2026-03-05 05:23:45+00:00" or similar
    try:
        # Try ISO format first
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00').replace('+00:00', ''))
    except:
        # Fallback: strip timezone and parse
        clean = ts_str.split('+')[0].split('Z')[0]
        return datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")


def synthesize_lifestyle_for_product(product: dict, theme: str = "Industrial Noir") -> tuple:
    """
    Synthesizes a lifestyle image for a product.
    Returns (local_path, cdn_url) or (None, None) on failure.
    """
    product_id = product.get('id')
    product_title = product.get('title', 'Unknown')
    images = product.get('images', [])
    
    if not images:
        _log(f"⚠️ No images for product {product_id}")
        return None, None
    
    # Get mockup URL
    mockup_url = images[0].get('src')
    for img in images:
        if 'front' in img.get('src', '').lower():
            mockup_url = img.get('src')
            break
    
    _log(f"// Synthesizing lifestyle for: {product_title}")
    
    # Fetch mockup image
    try:
        resp = requests.get(mockup_url)
        resp.raise_for_status()
        image_context = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        _log(f"⚠️ Failed to fetch mockup: {e}")
        return None, None
    
    # Build prompt
    prompt = (
        f"CBG Studio | Lifestyle Realization: A high-fidelity lifestyle photo. "
        f"The subject is the specific apparel product shown in the provided image. "
        f"CRITICAL: The product in the new photo must be EXACTLY identical to the base image. "
        f"You must replicate the pattern, colors, and placement with 100% precision. "
        f"Context: {theme} style. Visual Reference Style: industrial noir techwear aesthetic, "
        f"high-contrast shadows, clinical warehouse lighting. "
        f"The shot should be a medium close-up, focusing on the quality and design of the product specimen."
    )
    
    # Generate
    lifestyle_path = generate_nano_banana_image(
        prompt,
        graphic_type_override="mockups",
        image_context=image_context
    )
    
    if not lifestyle_path:
        return None, None
    
    # Apply stamp
    try:
        from scripts.fabricate_specimen_v2 import apply_unverified_stamp
        apply_unverified_stamp(lifestyle_path)
    except Exception as e:
        _log(f"⚠️ Stamp application failed: {e}")
    
    # Upload to Printify CDN
    fab = Fabricator()
    media_id = fab.upload_image(local_path=lifestyle_path, file_name=f"backfill_lifestyle_{product_id}.png")
    cdn_url = fab.last_upload_src
    
    # Rename folder to include product ID
    old_folder = Path(lifestyle_path).parent
    new_folder_name = f"{old_folder.name}__{product_id}"
    new_folder = old_folder.parent / new_folder_name
    try:
        old_folder.rename(new_folder)
    except:
        pass
    
    return lifestyle_path, cdn_url


def main():
    parser = argparse.ArgumentParser(description="Backfill missing blog posts for Printify products")
    parser.add_argument("--since", type=str, help="Cutoff datetime (default: 5am today)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without creating")
    parser.add_argument("--skip-lifestyle", action="store_true", help="Skip lifestyle generation, use Printify mockup")
    args = parser.parse_args()
    
    # Determine cutoff time
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
    else:
        # Default: 5am today
        today = datetime.now().replace(hour=5, minute=0, second=0, microsecond=0)
        cutoff = today
    
    _log(f"[SYSTEM_LOG]: BACKFILL_AUDIT // Cutoff: {cutoff}")
    _log("=" * 60)
    
    # Initialize
    fab = Fabricator()
    shopify = ShopifyConduit()
    
    # 1. Get all Printify products
    _log("// Fetching Printify products...")
    all_products = get_all_printify_products(fab)
    _log(f"// Total products: {len(all_products)}")
    
    # Filter to products created after cutoff (exclude templates)
    recent_products = []
    for p in all_products:
        if p.get('title', '').startswith('[TEMPLATE]:') or p.get('title', '').startswith('[DRAFT]'):
            continue
        created_at = p.get('created_at')
        if created_at:
            try:
                created_dt = parse_printify_timestamp(created_at)
                if created_dt >= cutoff:
                    recent_products.append(p)
            except Exception as e:
                _log(f"⚠️ Failed to parse timestamp for {p.get('id')}: {e}")
    
    _log(f"// Products since cutoff: {len(recent_products)}")
    
    if not recent_products:
        _log("[SYSTEM_LOG]: No recent products found. Nothing to backfill.")
        return 0
    
    # 2. Get blog posts from STATUS: UNVERIFIED
    _log("// Fetching Shopify blog articles...")
    blogs = shopify.list_blogs()
    blog_id = None
    for b in blogs:
        if b.get('title', '').strip() == '[STATUS: UNVERIFIED]':
            blog_id = b['id']
            break
    
    if not blog_id:
        _log("⚠️ [STATUS: UNVERIFIED] blog not found. Will create it.")
        if not args.dry_run:
            result = shopify._post('blogs.json', {'blog': {'title': '[STATUS: UNVERIFIED]'}})
            blog_id = result.get('blog', {}).get('id')
            _log(f"// Created blog ID: {blog_id}")
    
    # Get all articles
    articles = shopify.list_articles(blog_id, limit=250) if blog_id else []
    
    # Extract product IDs from article titles (format: "... | <product_id>" or direct product titles)
    article_product_ids = set()
    for art in articles:
        title = art.get('title', '')
        # Check if title contains a product ID (24-char hex)
        import re
        matches = re.findall(r'[0-9a-f]{24}', title.lower())
        article_product_ids.update(matches)
        # Also check body for product links
        body = art.get('body_html', '') or ''
        matches = re.findall(r'products/([0-9a-f]{24})', body.lower())
        article_product_ids.update(matches)
    
    _log(f"// Products with blog posts: {len(article_product_ids)}")
    
    # 3. Find products missing blog posts
    missing = []
    for p in recent_products:
        pid = p.get('id', '').lower()
        if pid not in article_product_ids:
            missing.append(p)
    
    _log(f"// Products MISSING blog posts: {len(missing)}")
    
    if not missing:
        _log("[SYSTEM_LOG]: All recent products have blog posts. Nothing to backfill.")
        return 0
    
    # 4. Display and optionally backfill
    _log("\n--- MISSING BLOG POSTS ---")
    for p in missing:
        _log(f"  [{p.get('id')}] {p.get('title')} (created: {p.get('created_at')})")
    
    if args.dry_run:
        _log("\n[DRY_RUN]: Would create blog posts for the above products.")
        return 0
    
    # 5. Backfill each missing product
    _log("\n--- BACKFILLING ---")
    created = 0
    failed = 0
    
    for p in missing:
        product_id = p.get('id')
        product_title = p.get('title', f'UNVERIFIED SPECIMEN: {product_id}')
        description = p.get('description', '')
        
        _log(f"\n// Processing: {product_title}")
        
        image_url = None
        
        if not args.skip_lifestyle:
            # Fetch full product details (for images)
            try:
                full_product = fab.get_product(product_id)
                _, cdn_url = synthesize_lifestyle_for_product(full_product)
                image_url = cdn_url
            except Exception as e:
                _log(f"⚠️ Lifestyle synthesis failed: {e}")
        
        if not image_url and not args.skip_lifestyle:
            _log("// Using Printify mockup as fallback...")
        
        # Fallback to Printify mockup
        if not image_url:
            images = p.get('images', [])
            if images:
                image_url = images[0].get('src')
        
        # Create blog post
        try:
            shopify.create_article(
                blog_id=blog_id,
                title=product_title,
                body_html=f"<p>{description}</p>" if description else "",
                image_url=image_url,
                author="CBG Studio",
                published=True,
            )
            _log(f"✅ Blog post created for {product_id}")
            created += 1
        except Exception as e:
            _log(f"❌ Failed to create blog post: {e}")
            failed += 1
    
    # Summary
    _log(f"\n{'=' * 60}")
    _log(f"[SUMMARY] Created: {created} | Failed: {failed}")
    _log("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
