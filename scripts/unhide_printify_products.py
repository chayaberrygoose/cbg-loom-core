"""
[FILE_ID]: unhide_printify_products.py // VERSION: 1.2 // STATUS: STABLE
Publish and unhide Printify products on Shopify.
- Paginates through all products in the Printify store
- Identifies products with visible=False (hidden from Shopify)
- Identifies unpublished products (no external link to Shopify)
- Publishes/republishes them to make them live on Shopify
- Automatically resumes: re-fetches product state each run, skips already-done
- Retries on 429 rate-limits with exponential backoff

Usage:
    python scripts/unhide_printify_products.py                      # publish all hidden + unpublished
    python scripts/unhide_printify_products.py --dry-run             # preview without changes
    python scripts/unhide_printify_products.py --hidden-only         # only unhide hidden products
    python scripts/unhide_printify_products.py --unpublished-only    # only publish unpublished products
"""
import os
import sys
import time
from pathlib import Path
import requests

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

sys.path.append(str(Path(__file__).parent))
from printify_markup import get_headers, get_shop_id, get_printify_api_key

BASE_URL = "https://api.printify.com/v1"


def get_printify_shop_id():
    return os.getenv("PRINTIFY_SHOP_ID") or os.getenv("printify_shop_id")


def get_all_products_paginated(shop_id):
    """Fetch all products across all pages. Retries on 429."""
    all_products = []
    page = 1
    while True:
        for attempt in range(5):
            resp = requests.get(
                f"{BASE_URL}/shops/{shop_id}/products.json",
                headers=get_headers(),
                params={"page": page},
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 0))
                wait = max(retry_after, 2 ** (attempt + 1) * 5)
                print(f"[RATE_LIMIT] 429 fetching page {page} — waiting {wait}s")
                time.sleep(wait)
                continue
            break
        if not resp.ok:
            print(f"[ERROR] {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])
        if not data:
            break
        all_products.extend(data)
        current_page = body.get("current_page", page)
        last_page = body.get("last_page", page)
        print(f"[SYSTEM_LOG] Fetched page {current_page}/{last_page} — {len(data)} products")
        if current_page >= last_page:
            break
        page += 1
        time.sleep(1)  # small delay between page fetches
    return all_products


def is_unpublished(product):
    """Product exists in Printify but was never published to Shopify."""
    external = product.get("external")
    # No external link at all, or external is empty/has no id
    if not external:
        return True
    if isinstance(external, dict) and not external.get("id"):
        return True
    return False


def is_hidden(product):
    """Product is published to Shopify but marked as not visible."""
    return not product.get("visible", True) and not is_unpublished(product)


def publish_product(shop_id, product_id, max_retries=5):
    """Publish a product to Shopify (makes it visible). Retries on 429."""
    url = f"{BASE_URL}/shops/{shop_id}/products/{product_id}/publish.json"
    headers = {
        "Authorization": f"Bearer {get_printify_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": True,
        "description": True,
        "images": True,
        "variants": True,
        "tags": True,
    }
    for attempt in range(max_retries):
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            # Respect Retry-After header if present, else exponential backoff
            retry_after = int(resp.headers.get("Retry-After", 0))
            wait = max(retry_after, 2 ** (attempt + 1) * 5)  # 10s, 20s, 40s, 80s, 160s
            print(f"[RATE_LIMIT] 429 on {product_id} — waiting {wait}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    # Final attempt after all retries exhausted
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp


def process_products(products, label, action_label, shop_id, dry_run):
    """Publish a list of products and print results."""
    if not products:
        print(f"[SYSTEM_LOG] No {label} products found.")
        return 0, 0

    print(f"\n// {label.upper()} PRODUCTS ({len(products)})")
    print("| # | Product ID | Title | Status |")
    print("|---|------------|-------|--------|")

    success = 0
    failed = 0

    for i, product in enumerate(products, 1):
        pid = product["id"]
        title = product.get("title", "Unknown")

        if dry_run:
            print(f"| {i} | {pid} | {title} | WOULD {action_label} |")
            continue

        try:
            publish_product(shop_id, pid)
            print(f"| {i} | {pid} | {title} | {action_label}D |")
            success += 1
            # Rate-limit: 3s between calls to stay under Printify limits
            time.sleep(3)
        except requests.HTTPError as e:
            print(f"| {i} | {pid} | {title} | FAILED ({e.response.status_code}) |")
            print(f"[ERROR] {e.response.text}")
            failed += 1
            # If still rate-limited after retries, pause longer before continuing
            if e.response.status_code == 429:
                print(f"[RATE_LIMIT] Pausing 60s before continuing...")
                time.sleep(60)

    return success, failed


def main():
    dry_run = "--dry-run" in sys.argv
    hidden_only = "--hidden-only" in sys.argv
    unpublished_only = "--unpublished-only" in sys.argv

    shop_id = get_printify_shop_id()
    if not shop_id:
        shop_id = get_shop_id()

    print(f"[SYSTEM_LOG] Shop ID: {shop_id}")
    print(f"[SYSTEM_LOG] Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"[SYSTEM_LOG] Fetching all products...")

    products = get_all_products_paginated(shop_id)
    print(f"[SYSTEM_LOG] Total products found: {len(products)}")

    hidden = [p for p in products if is_hidden(p)]
    unpublished = [p for p in products if is_unpublished(p)]

    print(f"[SYSTEM_LOG] Hidden products (visible=false): {len(hidden)}")
    print(f"[SYSTEM_LOG] Unpublished products (no Shopify link): {len(unpublished)}")

    total_success = 0
    total_failed = 0

    if not unpublished_only:
        s, f = process_products(hidden, "hidden", "UNHIDE", shop_id, dry_run)
        total_success += s
        total_failed += f

    if not hidden_only:
        s, f = process_products(unpublished, "unpublished", "PUBLISH", shop_id, dry_run)
        total_success += s
        total_failed += f

    target_count = 0
    if not unpublished_only:
        target_count += len(hidden)
    if not hidden_only:
        target_count += len(unpublished)

    if target_count == 0:
        print("\n[SYSTEM_LOG] No actionable products found. Nothing to do.")
        return

    print()
    if dry_run:
        print(f"[SYSTEM_LOG] Dry run complete. {target_count} products would be processed.")
    else:
        print(f"[SYSTEM_LOG] Complete. Success: {total_success} | Failed: {total_failed}")


if __name__ == "__main__":
    main()
