# [FILE_ID]: SYNC_CATALOG // VERSION: 3.6 // STATUS: STABLE
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
    