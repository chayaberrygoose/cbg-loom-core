import json
import os
import shutil
import requests
import urllib.parse
import sys

def sync(shop_id, token_path, output_dir):
    # Setup paths
    img_dir = os.path.join(output_dir, 'Product images')
    md_dir = os.path.join(output_dir, 'products_md')
    catalog_path = os.path.join(output_dir, 'catalog.md')
    products_json_path = os.path.join(output_dir, 'products.json')

    # 1. Cleanup old version (including images)
    print("Cleaning up old catalog and images...")
    if os.path.exists(img_dir):
        shutil.rmtree(img_dir)
    if os.path.exists(md_dir):
        shutil.rmtree(md_dir)
    if os.path.exists(catalog_path):
        os.remove(catalog_path)
    
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)

    # 2. Fetch products
    print(f"Fetching products for shop {shop_id}...")
    try:
        with open(token_path, 'r') as f:
            token = f.read().strip()
    except Exception as e:
        print(f"Error reading token from {token_path}: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Save products.json for reference
        with open(products_json_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error fetching products: {e}")
        return

    products = data.get('data', [])
    print(f"Syncing {len(products)} products...")

    catalog_rows = []

    for p in products:
        title = p.get('title', 'Unknown')
        description = p.get('description', 'No description available.')
        tags = p.get('tags', [])
        product_id = p.get('id', 'N/A')
        blueprint_id = p.get('blueprint_id', 'N/A')
        
        # Sanitize for filename
        clean_filename = "".join([c if c.isalnum() else "_" for c in title])[:50]
        md_filename = f"{clean_filename}.md"
        
        # Price
        price = "N/A"
        if p.get('variants'):
            price = f"${p['variants'][0].get('price', 0) / 100:.2f}"

        # Build product page
        md_content = [f"# {title}", 
                      f"**Price:** {price}",
                      f"**Product ID:** `{product_id}`",
                      f"**Blueprint ID:** `{blueprint_id}`",
                      f"## Description\n{description}\n"]
        if tags:
            md_content.append(f"## Keywords\n`{', '.join(tags)}`\n")
        md_content.append("## Gallery\n")

        image_previews = []
        for i, img_obj in enumerate(p.get('images', [])):
            img_url = img_obj.get('src')
            if not img_url: continue
            
            img_filename = f"{clean_filename}_{i}.jpg"
            img_path = os.path.join(img_dir, img_filename)
            
            # Download image
            try:
                img_res = requests.get(img_url, stream=True)
                if img_res.status_code == 200:
                    with open(img_path, 'wb') as f_img:
                        for chunk in img_res.iter_content(1024):
                            f_img.write(chunk)
            except:
                pass
            
            # Link for individual MD (relative)
            indiv_rel_img = urllib.parse.quote(f"../Product images/{img_filename}")
            md_content.append(f"![{title} {i}]({indiv_rel_img})\n")
            
            # For catalog preview (first 2 images)
            if i < 2:
                cat_rel_img = urllib.parse.quote(f"Product images/{img_filename}")
                image_previews.append(f"![{title.replace('|', '&#124;')}]({cat_rel_img})")

        # Write individual MD
        with open(os.path.join(md_dir, md_filename), 'w') as f_md:
            f_md.write("\n".join(md_content))
            
        # Catalog Row
        title_for_table = title.replace('|', '&#124;')
        catalog_link = urllib.parse.quote(f"products_md/{md_filename}")
        catalog_rows.append(f"| [{title_for_table}]({catalog_link}) | `{product_id}` | `{blueprint_id}` | {price} | {' '.join(image_previews)} |")

    # Write catalog.md
    with open(catalog_path, 'w') as f_cat:
        f_cat.write("### Product Catalog\n\n")
        f_cat.write("| Product Name | Product ID | Blueprint ID | Price (MSRP) | Image Previews |\n")
        f_cat.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for row in catalog_rows:
            f_cat.write(f"{row}\n")

    print(f"Success: Catalog updated with {len(products)} products.")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: sync_catalog.py <shop_id> <token_path> <output_dir>")
    else:
        sync(sys.argv[1], sys.argv[2], sys.argv[3])
