# [FILE_ID]: SYNC_CATALOG // VERSION: 3.5 // STATUS: STABLE
import json
import os
import shutil
import requests
import urllib.parse
import sys
import re

# Cache for blueprint info to avoid redundant API calls
BLUEPRINT_CACHE = {}

def get_blueprint_info(blueprint_id, headers):
    if blueprint_id in BLUEPRINT_CACHE:
        return BLUEPRINT_CACHE[blueprint_id]
        
    url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}.json"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            BLUEPRINT_CACHE[blueprint_id] = data
            return data
    except Exception as e:
        print(f"Error fetching blueprint {blueprint_id}: {e}")
    
    return {"description": "No blueprint description available."}

def sync(shop_id, token_path, output_dir):
    # Setup paths
    catalog_path = os.path.join(output_dir, 'catalog.md')
    products_json_path = os.path.join(output_dir, 'products.json')

    # 1. Cleanup old version
    print("Cleaning up old catalog content...")
    # List all entries in output_dir and remove directories (except hidden ones)
    if os.path.exists(output_dir):
        for entry in os.listdir(output_dir):
            full_path = os.path.join(output_dir, entry)
            if os.path.isdir(full_path) and not entry.startswith('.'):
                shutil.rmtree(full_path)
            elif entry == 'catalog.md':
                os.remove(full_path)
    
    os.makedirs(output_dir, exist_ok=True)

    # 2. Fetch products
    print(f"Fetching products for shop {shop_id}...")
    token = os.environ.get('PRINTIFY_API_TOKEN')
    
    if not token:
        try:
            with open(token_path, 'r') as f:
                token = f.read().strip()
        except Exception as e:
            print(f"Error: PRINTIFY_API_TOKEN not set and could not read from {token_path}: {e}")
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
        product_id = p.get('id', 'N/A')
        blueprint_id = p.get('blueprint_id', 'N/A')
        
        # Get Blueprint info for the product (Used for Description, Care, and Specs)
        blueprint_info = get_blueprint_info(blueprint_id, headers)
        
        # Sourcing description and care instructions from the BLUEPRINT not the product
        blueprint_raw_description = blueprint_info.get('description', '')
        
        # Clean HTML from blueprint description
        def clean_html(text):
            return re.sub('<[^<]+?>', '', text).replace('.:', '- ').strip()

        description = clean_html(blueprint_raw_description)
        care_instructions = ""
        
        # Check if the blueprint description actually contains care info (sometimes it does in a list)
        if "Care instructions" in blueprint_raw_description:
            parts = blueprint_raw_description.split("Care instructions")
            description = clean_html(parts[0])
            care_instructions = clean_html(parts[1])
        elif "Printed care label" in blueprint_raw_description:
            # If it just mentions a care label, we'll keep that as a note in care section if user prefers, 
            # but for now we'll just let it be part of the description as per blueprint default.
            pass

        tags = p.get('tags', [])
        
        # Determine Status: If it has an external ID, it is considered published.
        external = p.get('external', {})
        is_published = bool(external.get('id'))
        status_text = "PUBLISHED" if is_published else "UNPUBLISHED"
        
        # Create product-specific directory
        product_dir = os.path.join(output_dir, product_id)
        os.makedirs(product_dir, exist_ok=True)

        # Sanitize for filename
        clean_filename = "".join([c if c.isalnum() else "_" for c in title])[:50]
        md_filename = f"{clean_filename}.md"
        
        # Build product page
        md_content = [f"# {title}", 
                      f"**Status:** `{status_text}`",
                      f"**Product ID:** `{product_id}`",
                      f"**Blueprint ID:** `{blueprint_id}`",
                      f"## Description\n{description}\n"]
        
        if care_instructions:
            md_content.append(f"## Care Instructions\n{care_instructions}\n")
            
        # Tag and Description synthesis
        if tags:
            md_content.append(f"## Keywords\n`{', '.join(tags)}`\n")
        
        # Add Blueprint Specifications
        # (Already fetched via blueprint_info earlier in the loop)
        
        md_content.append("## Gallery\n")

        image_previews = []
        for i, img_obj in enumerate(p.get('images', [])):
            img_url = img_obj.get('src')
            if not img_url: continue
            
            img_filename = f"{clean_filename}_{i}.jpg"
            img_path = os.path.join(product_dir, img_filename)
            
            # Download image
            try:
                img_res = requests.get(img_url, stream=True)
                if img_res.status_code == 200:
                    with open(img_path, 'wb') as f_img:
                        for chunk in img_res.iter_content(1024):
                            f_img.write(chunk)
            except:
                pass
            
            # Link for individual MD (relative - same folder)
            indiv_rel_img = urllib.parse.quote(img_filename)
            md_content.append(f"![{title} {i}]({indiv_rel_img})\n")
            
            # For catalog preview (first 2 images - relative to output_dir)
            if i < 2:
                cat_rel_img = urllib.parse.quote(f"{product_id}/{img_filename}")
                image_previews.append(f"![{title.replace('|', '&#124;')}]({cat_rel_img})")

        # Append Blueprint Specifications at the end
        blueprint_desc_raw = blueprint_info.get('description', 'No blueprint description available.')
        md_content.append(f"\n## Blueprint Specifications\n{blueprint_desc_raw}\n")

        # Write individual MD
        with open(os.path.join(product_dir, md_filename), 'w') as f_md:
            f_md.write("\n".join(md_content))
            
        # Catalog Row
        title_for_table = title.replace('|', '&#124;')
        catalog_link = urllib.parse.quote(f"{product_id}/{md_filename}")
        catalog_rows.append(f"| [{title_for_table}]({catalog_link}) | `{status_text}` | `{product_id}` | `{blueprint_id}` | {' '.join(image_previews)} |")

    # Write catalog.md
    with open(catalog_path, 'w') as f_cat:
        f_cat.write("### Product Catalog\n\n")
        f_cat.write("| Product Name | Status | Product ID | Blueprint ID | Image Previews |\n")
        f_cat.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for row in catalog_rows:
            f_cat.write(f"{row}\n")

    print(f"Success: Catalog updated with {len(products)} products.")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Assuming token is in environment
        sync(sys.argv[1], "", sys.argv[2])
    elif len(sys.argv) == 4:
        sync(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: sync_catalog.py <shop_id> [token_path] <output_dir>")
        print("Note: If token_path is omitted, PRINTIFY_API_TOKEN environment variable must be set.")
