"""
/* [FILE_ID]: FABRICATOR // VERSION: 1.0 // STATUS: UNSTABLE */
This module handles the cloning of Printify products with new swatches.
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

class Fabricator:
    BASE_URL = "https://api.printify.com/v1"
    
    def __init__(self, shop_id: str = "12043562"):
        self.shop_id = shop_id
        self.token = self._load_token()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _load_token(self) -> str:
        """Loads the Printify API token from the environment file."""
        # Assuming run from repo root or similar structure
        # Adjust path logic as needed based on where this script is called
        current_file = Path(__file__)
        # Walk up to finding .env or similar. 
        # Based on previous context: /home/cbg/repos/cbg-loom-core/.env/printify_api_token.txt
        # If this file is in agents/skills/fabricator/fabricator.py
        # root is 3 levels up
        root_dir = current_file.parent.parent.parent.parent
        # Check for both spellings (typo handling)
        token_path = root_dir / ".env" / "printify_api_token.txt"
        if not token_path.exists():
            token_path = root_dir / ".env" / "prinitfy_api_token.txt"
        
        if not token_path.exists():
             # Fallback: try to find it in the current working directory or standard locations
             token_path = Path(".env/printify_api_token.txt")
        
        if not token_path.exists():
            raise FileNotFoundError(f"EARTH_BREACH: Token not found at {token_path}")
            
        return token_path.read_text().strip()

    def get_product(self, product_id: str) -> Dict[str, Any]:
        """Retrieves a specific product to use as a template."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def upload_image(self, image_url: str, file_name: str = "fabricated_specimen.png") -> str:
        """
        Uploads an image via URL to Printify Media Library.
        Returns the new image ID.
        """
        url = f"{self.BASE_URL}/uploads/images.json"
        payload = {
            "file_name": file_name,
            "url": image_url
        }
        print(f"// UPLOADING_ARTIFACT: {image_url}")
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        print(f"// ARTIFACT_SECURED: ID {data['id']}")
        return data['id']

    def clone_product(self, source_product_id: str, new_image_url: str, title_suffix: str = " [CLONE]") -> Dict[str, Any]:
        """
        Clones a product's positioning but swaps the image.
        """
        print(f"--- [FABRICATION_START]: SOURCE_{source_product_id} ---")
        
        # 1. Get Source
        source = self.get_product(source_product_id)
        
        # 2. Upload New Image
        new_image_id = self.upload_image(new_image_url)
        
        # 3. Construct Payload
        # We need specific variants. For a true clone, we might want to enable all variants
        # that were enabled in the source, or just use the blueprint defaults.
        # Printify creation requires blueprint_id, print_provider_id, variants, print_areas.
        
        # Extract variant IDs to enable (simplified: just enable all blueprint variants or specific ones)
        # For this prototype, we will map the source variants to the new product request.
        # However, creating a product usually just needs the blueprint/provider and variant definitions.
        
        print_areas = source.get('print_areas', [])
        new_print_areas = []

        for area in print_areas:
            new_placeholders = []
            for placeholder in area.get('placeholders', []):
                images = placeholder.get('images', [])
                if not images:
                    continue
                
                # [PROTOCOL_UPDATE]: Multi-Layer Logic
                # Layer 0 is the base pattern/swatch (replaced).
                # Layers 1+ are overlays (preserved, e.g., logos).
                
                new_images_list = []
                
                # LAYER 0: The Base Swatch
                base_img = images[0]
                new_base_obj = {
                    "id": new_image_id,
                    "x": base_img.get('x', 0.5),
                    "y": base_img.get('y', 0.5),
                    "scale": base_img.get('scale', 1),
                    "angle": base_img.get('angle', 0)
                }
                if 'pattern' in base_img:
                    new_base_obj['pattern'] = base_img['pattern']
                new_images_list.append(new_base_obj)

                # LAYER 1+: Overlays
                if len(images) > 1:
                    for overlay_img in images[1:]:
                        new_images_list.append(overlay_img)
                
                new_placeholders.append({
                    "position": placeholder.get('position'),
                    "images": new_images_list
                })
            
            new_print_areas.append({
                "variant_ids": area.get('variant_ids'),
                "placeholders": new_placeholders,
                "background": area.get('background') # Keep background color
            })

        # Variants construction
        # We need to send a list of variants. 
        # Often safest to just send the IDs we want to exist.
        variants = []
        for v in source.get('variants', []):
            if v.get('is_enabled', True):
                variants.append({"id": v['id'], "price": v['price'], "is_enabled": True})

        payload = {
            "title": source.get('title') + title_suffix,
            "description": source.get('description'),
            "blueprint_id": source.get('blueprint_id'),
            "print_provider_id": source.get('print_provider_id'),
            "variants": variants,
            "print_areas": new_print_areas
        }
        
        # 4. Create Product
        print("// INJECTING_SCHEMATIC...")
        create_url = f"{self.BASE_URL}/shops/{self.shop_id}/products.json"
        response = requests.post(create_url, json=payload, headers=self.headers)
        
        try:
            response.raise_for_status()
            product = response.json()
            print(f"--- [FABRICATION_COMPLETE]: ID_{product['id']} ---")
            return product
        except requests.exceptions.HTTPError as e:
            print(f"!! [SYSTEM_FAILURE]: {response.text}")
            raise e

if __name__ == "__main__":
    # Example Usage (Commented out to prevent accidental execution)
    # fab = Fabricator()
    # fab.clone_product("66fb...", "https://...")
    pass
