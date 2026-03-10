/* [FILE_ID]: printify_markup.py // VERSION: 1.0 // STATUS: STABLE */
"""
Script to fetch Printify product(s), calculate a 30% markup for each variant, and print the results.
Requires PRINTIFY_API_KEY as an environment variable.
"""
import os
import requests
import sys

PRINTIFY_API_KEY = os.getenv("PRINTIFY_API_KEY")
BASE_URL = "https://api.printify.com/v1"
HEADERS = {"Authorization": f"Bearer {PRINTIFY_API_KEY}"}

def get_shop_id():
    resp = requests.get(f"{BASE_URL}/shops.json", headers=HEADERS)
    resp.raise_for_status()
    shops = resp.json()
    if not shops:
        raise Exception("No shops found for this account.")
    return shops[0]["id"]

def get_product(shop_id, product_id):
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}/products/{product_id}.json", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def get_all_products(shop_id):
    resp = requests.get(f"{BASE_URL}/shops/{shop_id}/products.json", headers=HEADERS)
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
