import os
import requests
import sys


BASE_URL = "https://api.printify.com/v1"

def get_printify_api_key():
    # Support both uppercase and lowercase keys
    return os.getenv("PRINTIFY_API_KEY") or os.getenv("printify_api_key")

def get_headers():
    api_key = get_printify_api_key()
    if not api_key:
        raise RuntimeError("PRINTIFY_API_KEY is not set in environment.")
    return {"Authorization": f"Bearer {api_key}"}

def get_shop_id():
    resp = requests.get(f"{BASE_URL}/shops.json", headers=get_headers())
    resp.raise_for_status()
    shops = resp.json()
    if not shops:
        raise Exception("No shops found for this account.")
    return shops[0]["id"]

def get_product(shop_id, product_id):
    import requests
    url = f"{BASE_URL}/shops/{shop_id}/products/{product_id}.json"
    try:
        resp = requests.get(url, headers=get_headers())
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"[PRINTIFY ERROR] Failed to fetch product {product_id} from shop {shop_id}.")
        print(f"[PRINTIFY ERROR] Status: {e.response.status_code}")
        print(f"[PRINTIFY ERROR] URL: {url}")
        print(f"[PRINTIFY ERROR] Response: {e.response.text}")
        raise

def get_all_products(shop_id):
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}/products.json", headers=get_headers())
    resp.raise_for_status()
    return resp.json()["data"]

def apply_markup_to_variants(product, markup=0.3):
    result = []
    for variant in product.get("variants", []):
        try:
            base_price = float(variant["price"])
            marked_up_price = round(base_price * (1 + markup), 2)
            result.append({
                "variant_id": variant["id"],
                "title": variant.get("title", ""),
                "base_price": base_price,
                "marked_up_price": marked_up_price
            })
        except Exception as e:
            print(f"[ERROR] Could not process variant {variant.get('id')}: {e}")
    return result

def print_markup_table(product, markup=0.3):
    print(f"Product: {product.get('title', 'Unknown')}")
    print("| Variant ID | Title | Base Price | Marked-up Price |")
    print("|------------|-------|------------|-----------------|")
    for v in apply_markup_to_variants(product, markup):
        print(f"| {v['variant_id']} | {v['title']} | {v['base_price']} | {v['marked_up_price']} |")
    print()

def process_single_product(product_id, markup=0.3):
    shop_id = get_shop_id()
    product = get_product(shop_id, product_id)
    print_markup_table(product, markup)

def process_all_products(markup=0.3):
    shop_id = get_shop_id()
    products = get_all_products(shop_id)
    for prod in products:
        product = get_product(shop_id, prod["id"])
        print_markup_table(product, markup)

def main():
    if not PRINTIFY_API_KEY:
        print("[ERROR] PRINTIFY_API_KEY environment variable not set.")
        sys.exit(1)
    if len(sys.argv) > 1:
        product_id = sys.argv[1]
        process_single_product(product_id)
    else:
        process_all_products()

if __name__ == "__main__":
    main()
