import json
import os
import requests
import time

def get_blueprint_info(blueprint_id, headers):
    url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}.json"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            return data.get('title', f"Blueprint {blueprint_id}"), data.get('description', '')
    except Exception as e:
        print(f"Error fetching blueprint {blueprint_id}: {e}")
    return f"Blueprint {blueprint_id}", ""

def main():
    # Load token
    token_path = ".env/printify_api_key.txt"
    try:
        with open(token_path, 'r') as f:
            token = f.read().strip()
    except Exception as e:
        print(f"Error reading token: {e}")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    shop_id = "12043562"

    # Load products
    products_path = "artifacts/catalog/products.json"
    try:
        with open(products_path, 'r') as f:
            data = json.load(f)
            products = data.get('data', [])
    except Exception as e:
        print(f"Error reading products.json: {e}")
        return

    print(f"Found {len(products)} products to clone as templates.")

    for p in products:
        source_id = p.get('id')
        blueprint_id = p.get('blueprint_id')
        print_provider_id = p.get('print_provider_id')
        
        print(f"\nProcessing {source_id} (Blueprint: {blueprint_id})...")
        
        # Get blueprint info
        blueprint_name, blueprint_desc = get_blueprint_info(blueprint_id, headers)
        new_title = f"[TEMPLATE]: {blueprint_name}"
        
        # Construct variants
        variants = []
        for v in p.get('variants', []):
            if v.get('is_enabled', True):
                variants.append({
                    "id": v['id'], 
                    "price": v['price'], 
                    "is_enabled": True
                })
                
        # Construct print_areas
        # We need to clean up the print_areas to match what the API expects for creation
        # Specifically, we just need variant_ids, placeholders (with position and images)
        new_print_areas = []
        for area in p.get('print_areas', []):
            new_placeholders = []
            for ph in area.get('placeholders', []):
                new_images = []
                for img in ph.get('images', []):
                    img_data = {
                        "id": img['id'],
                        "x": img.get('x', 0.5),
                        "y": img.get('y', 0.5),
                        "scale": img.get('scale', 1.0),
                        "angle": img.get('angle', 0)
                    }
                    if 'pattern' in img:
                        img_data['pattern'] = img['pattern']
                    if 'height' in img:
                        img_data['height'] = img['height']
                    if 'width' in img:
                        img_data['width'] = img['width']
                    new_images.append(img_data)
                
                # Only add placeholder if it has images
                if new_images:
                    new_placeholders.append({
                        "position": ph.get('position'),
                        "images": new_images
                    })
            
            new_print_areas.append({
                "variant_ids": area.get('variant_ids', []),
                "placeholders": new_placeholders,
                "background": area.get('background', '#ffffff')
            })

        payload = {
            "title": new_title,
            "description": blueprint_desc if blueprint_desc else p.get('description', ''),
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants,
            "print_areas": new_print_areas
        }

        # Create product
        create_url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
        try:
            response = requests.post(create_url, json=payload, headers=headers)
            response.raise_for_status()
            new_product = response.json()
            print(f"Success! Created template: {new_product['id']} - {new_title}")
        except requests.exceptions.HTTPError as e:
            print(f"Failed to create template for {source_id}: {response.text}")
        
        # Sleep briefly to avoid rate limits
        time.sleep(1)

if __name__ == "__main__":
    main()
