"""
[FILE_ID]: publish_printify_product.py // VERSION: 0.2 // STATUS: UNSTABLE
Publication flow for Printify → Shopify:
- Takes Printify Product ID as argument
- Sets 30% margin for all variants
- Publishes product (Printify → Shopify)
- Waits for Shopify listing
- Uploads lifestyle image to Shopify and sets as primary
"""
import os
import sys
import time
from pathlib import Path
import requests

# Ensure .env is loaded for all environment variables
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

# Import Printify helpers from scripts/printify_markup.py
sys.path.append(str(Path(__file__).parent))
from printify_markup import get_shop_id, get_product, get_printify_api_key
# Import ShopifyConduit from agents.skills.shopify_skill
sys.path.append(str(Path(__file__).parent.parent))
from agents.skills.shopify_skill import ShopifyConduit

def get_env(*keys):
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None

# Support both lowercase and uppercase .env keys
PRINTIFY_API_KEY = get_env("PRINTIFY_API_KEY", "printify_api_key")
SHOPIFY_STORE_URL = get_env("SHOPIFY_STORE_URL", "shopify_store_url")
SHOPIFY_ACCESS_TOKEN = get_env("SHOPIFY_ACCESS_TOKEN", "shopify_access_token")

print(f"[DEBUG] PRINTIFY_API_KEY: {PRINTIFY_API_KEY}")
print(f"[DEBUG] SHOPIFY_STORE_URL: {SHOPIFY_STORE_URL}")
print(f"[DEBUG] SHOPIFY_ACCESS_TOKEN: {SHOPIFY_ACCESS_TOKEN}")
if not PRINTIFY_API_KEY:
    print("[ERROR] PRINTIFY_API_KEY is not set. Check .env and environment.")
    sys.exit(1)

def get_printify_shop_id():
    # Support both uppercase and lowercase keys
    return os.getenv("PRINTIFY_SHOP_ID") or os.getenv("printify_shop_id")

def set_margin_and_publish(product_id, margin=0.3):
    shop_id = get_printify_shop_id()
    if not shop_id:
        shop_id = get_shop_id()
    print(f"[DEBUG] Using Printify shop_id: {shop_id}")
    print(f"[DEBUG] Getting product: shop_id={shop_id}, product_id={product_id}")
    import requests
    try:
        product = get_product(shop_id, product_id)
    except requests.HTTPError as e:
        print(f"[PRINTIFY ERROR] Failed to fetch product {product_id} from shop {shop_id}.")
        print(f"[PRINTIFY ERROR] Status: {e.response.status_code}")
        print(f"[PRINTIFY ERROR] URL: {e.response.url}")
        print(f"[PRINTIFY ERROR] Response: {e.response.text}")
        raise
    # Update all variants with new price
    updates = []
    for variant in product.get("variants", []):
        # Use production cost as base for profit margin
        if "cost" in variant and variant["cost"] is not None:
            base_price = float(variant["cost"])
        else:
            print(f"[WARN] Variant {variant['id']} missing 'cost', using 'price' as fallback.")
            base_price = float(variant["price"])
        # Profit margin: price = cost / (1 - margin)
        marked_up_price = int(round(base_price / (1 - margin)))
        updates.append({"id": variant["id"], "price": marked_up_price})
    # Update product variants
    url = f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json"
    headers = {"Authorization": f"Bearer {get_printify_api_key()}", "Content-Type": "application/json"}
    try:
        resp = requests.put(url, headers=headers, json={"variants": updates})
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"[PRINTIFY ERROR] Failed to update product {product_id}.")
        print(f"[PRINTIFY ERROR] Status: {e.response.status_code}")
        print(f"[PRINTIFY ERROR] URL: {e.response.url}")
        print(f"[PRINTIFY ERROR] Response: {e.response.text}")
        raise
    # Fetch product details for publish payload
    product_url = f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json"
    try:
        prod_resp = requests.get(product_url, headers=headers)
        prod_resp.raise_for_status()
        product_data = prod_resp.json()
    except requests.HTTPError as e:
        print(f"[PRINTIFY ERROR] Failed to fetch product details for publish.")
        print(f"[PRINTIFY ERROR] Status: {e.response.status_code}")
        print(f"[PRINTIFY ERROR] URL: {e.response.url}")
        print(f"[PRINTIFY ERROR] Response: {e.response.text}")
        raise

    # Build publish payload
    # Printify publish expects booleans for which fields to publish
    publish_payload = {
        "title": True,
        "description": True,
        "images": True,
        "variants": True,
        "tags": True,
        "publish": {"shop": "shopify"}
    }

    # Publish product
    pub_url = f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}/publish.json"
    try:
        pub_resp = requests.post(pub_url, headers=headers, json=publish_payload)
        pub_resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"[PRINTIFY ERROR] Failed to publish product {product_id}.")
        print(f"[PRINTIFY ERROR] Status: {e.response.status_code}")
        print(f"[PRINTIFY ERROR] URL: {e.response.url}")
        print(f"[PRINTIFY ERROR] Response: {e.response.text}")
        raise

    return True

def wait_for_printify_publish(shop_id, product_id, timeout=300, poll_interval=10):
    """
    Poll Printify product until it is published to Shopify (status: 'published' or similar).
    """
    import requests
    elapsed = 0
    import dateutil.parser
    def iso8601(dt):
        try:
            return dateutil.parser.isoparse(dt) if dt else None
        except Exception:
            return None
    while elapsed < timeout:
        url = f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json"
        headers = {"Authorization": f"Bearer {get_printify_api_key()}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        external = data.get("external", {})
        status = data.get("status")
        is_locked = data.get("is_locked", False)
        updated_at = iso8601(data.get("updated_at"))
        synced_at = iso8601(data.get("synced_at"))
        ext_updated_at = iso8601(external.get("updated_at")) if external.get("updated_at") else None
        error = data.get("error")
        # Sync in progress if status is publishing/pending, is_locked, or updated_at > synced_at
        sync_in_progress = False
        if status in ["publishing", "pending"]:
            sync_in_progress = True
        if is_locked:
            sync_in_progress = True
        if updated_at and synced_at and updated_at > synced_at:
            sync_in_progress = True
        if updated_at and ext_updated_at and updated_at > ext_updated_at:
            sync_in_progress = True
        if error:
            raise RuntimeError(f"[PRINTIFY ERROR] Sync failed: {error}")
        if not sync_in_progress:
            print(f"[SYSTEM_LOG] Printify product {product_id} sync complete. Proceeding.")
            return
        print(f"[SYSTEM_LOG] Waiting for Printify to finish publishing {product_id}... [status={status}, is_locked={is_locked}, updated_at={updated_at}, synced_at={synced_at}, ext.updated_at={ext_updated_at}]")
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Printify product {product_id} not published after {timeout} seconds (sync not complete).")
def wait_for_shopify_product(printify_product_id, timeout=300, poll_interval=10):
    conduit = ShopifyConduit()
    elapsed = 0
    while elapsed < timeout:
        products = conduit.list_products(limit=250)
        for p in products:
            if (
                str(printify_product_id) in str(p.get("body_html", ""))
                or str(printify_product_id) in str(p.get("title", ""))
                or str(printify_product_id) == str(p.get("id"))
            ):
                return p["id"]
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError("Shopify product not found after publish.")

def find_lifestyle_image(product_id):
    # 1. Check local mockups folder for direct file
    mockup_dir = Path("artifacts/graphics/mockups")
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        candidate = mockup_dir / f"{product_id}{ext}"
        if candidate.exists():
            return str(candidate)
    # 2. Check subfolders whose name ends with __<product_id>
    for sub in mockup_dir.iterdir():
        if sub.is_dir() and sub.name.endswith(f"__{product_id}"):
            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                for img in sub.iterdir():
                    if img.suffix.lower() == ext:
                        return str(img)
            # fallback: return any image file in the folder
            for img in sub.iterdir():
                if img.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    return str(img)
    # 3. Fallback: try to fetch from Shopify blog (not implemented)
    return None

def upload_lifestyle_image(shopify_product_id, image_path):
    # conduit = ShopifyConduit()  # Not needed for direct REST call
    with open(image_path, "rb") as f:
        image_data = f.read()
    # Shopify API expects base64 or URL, so upload via REST
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-01/products/{shopify_product_id}/images.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
    import base64
    encoded = base64.b64encode(image_data).decode()
    payload = {"image": {"attachment": encoded, "position": 1}}
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def list_printify_products():
    shop_id = get_printify_shop_id()
    if not shop_id:
        shop_id = get_shop_id()
    print(f"[DEBUG] Listing products for Printify shop_id: {shop_id}")
    from printify_markup import get_all_products
    products = get_all_products(shop_id)
    for prod in products:
        print(f"Product ID: {prod['id']} | Title: {prod.get('title', '')}")

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--list-products':
        list_printify_products()
        sys.exit(0)
    if len(sys.argv) != 2:
        print("Usage: python scripts/publish_printify_product.py <PRINTIFY_PRODUCT_ID>")
        print("       python scripts/publish_printify_product.py --list-products")
        sys.exit(1)
    product_id = sys.argv[1]
    print(f"[SYSTEM_LOG] Setting margin and publishing Printify product {product_id}...")
    set_margin_and_publish(product_id)
    shop_id = get_printify_shop_id() or get_shop_id()
    wait_for_printify_publish(shop_id, product_id)
    print(f"[SYSTEM_LOG] Waiting for Shopify product to appear...")
    shopify_product_id = wait_for_shopify_product(product_id)
    print(f"[SYSTEM_LOG] Shopify product ID: {shopify_product_id}")
    image_path = find_lifestyle_image(product_id)
    if not image_path:
        print(f"[SYSTEM_LOG] Lifestyle image not found for {product_id}.")
        sys.exit(1)
    print(f"[SYSTEM_LOG] Uploading lifestyle image {image_path} to Shopify...")
    upload_lifestyle_image(shopify_product_id, image_path)
    print(f"[SYSTEM_LOG] Publication flow complete.")

if __name__ == "__main__":
    main()
