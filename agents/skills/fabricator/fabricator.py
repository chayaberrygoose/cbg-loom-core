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
        # Based on previous context: ~/repos/cbg-loom-core/.env/printify_api_token.txt
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

    def clone_product(self, source_product_id: str, new_image_url: str, title_suffix: str = " [CLONE]", preserve_logo_only: bool = False, logo_id: str = None, trim_image_url: str = None) -> Dict[str, Any]:
        """
        Clones a product's positioning but swaps the image.
        
        Args:
            source_product_id: ID of the product to copy.
            new_image_url: URL of the new texture/swatch (Body).
            title_suffix: String to append to the new title.
            preserve_logo_only: If True, operates in aggressive mode replacing everything except logo_id.
            logo_id: The specific image ID to treat as the protected logo.
            trim_image_url: [OPTIONAL] URL of a second texture for trim (cuffs, waistband, etc.).
                            If provided, any artifact that is NOT the Main Swatch and NOT the Logo gets this texture.
                            If NOT provided, trim gets the Main Swatch (in aggressive mode) or is preserved (in conservative mode).
        """
        print(f"--- [FABRICATION_START]: SOURCE_{source_product_id} ---")
        
        # 1. Get Source
        source = self.get_product(source_product_id)
        
        # 2. Upload Artifacts
        new_image_id = self.upload_image(new_image_url, "fabricated_body.png")
        trim_image_id = None
        if trim_image_url:
            trim_image_id = self.upload_image(trim_image_url, "fabricated_trim.png")
            print(f"// SECONDARY_ARTIFACT_SECURED: TRIM_ID_{trim_image_id}")
        
        # [PROTOCOL_UPDATE]: Genetic Marker Logic (Universal Scanner)
        source_main_id = None
        
        # Identification Logic: Scan ALL areas to find the most frequent Image ID (The Dominant Gene)
        image_frequency = {}
        
        for area in source.get('print_areas', []):
            for ph in area.get('placeholders', []):
                images = ph.get('images', [])
                if not images:
                    continue
                
                # Assume the first image (Layer 0) is the base fabric in most cases
                base_img_id = images[0]['id']
                image_frequency[base_img_id] = image_frequency.get(base_img_id, 0) + 1
        
        # The ID with the highest frequency is likely the main body fabric
        if image_frequency:
             source_main_id = max(image_frequency, key=image_frequency.get)
        
        print(f"// GENETIC_MARKER_IDENTIFIED: MAIN_ID_{source_main_id} (Frequency: {image_frequency.get(source_main_id, 0)})")
        if preserve_logo_only and logo_id:
             print(f"// SELECTIVE_PRESERVATION: PROTECTING_LOGO_ID_{logo_id}")

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
                
                # [PROTOCOL_UPDATE]: Multi-Layer & Distinct Artifact Logic
                new_images_list = []
                
                # Iterate through all images in this placeholder (Layers)
                for index, original_img in enumerate(images):
                    
                    original_id = original_img.get('id')
                    replacement_id = None # If None, preserve original
                    
                    if preserve_logo_only:
                        # AGGRESSIVE MODE
                        if original_id == logo_id:
                             # Protect Logo -> Preserve
                             replacement_id = None
                        elif original_id == source_main_id:
                             # Main Body -> New Body Texture
                             replacement_id = new_image_id
                        else:
                             # Trim/Artifacts -> Trim Texture (if exists) OR Body Texture
                             replacement_id = trim_image_id if trim_image_id else new_image_id

                    else:
                        # CONSERVATIVE MODE
                        if original_id == source_main_id:
                            # Main Body -> New Body Texture
                            replacement_id = new_image_id
                        else:
                            # Trim/Logos -> Preserve Original
                            replacement_id = None

                    if replacement_id:
                        # REPLACE
                        new_base_obj = {
                            "id": replacement_id,
                            "x": original_img.get('x', 0.5),
                            "y": original_img.get('y', 0.5),
                            "scale": original_img.get('scale', 1),
                            "angle": original_img.get('angle', 0)
                        }
                        if 'pattern' in original_img:
                            new_base_obj['pattern'] = original_img['pattern']
                        new_images_list.append(new_base_obj)
                    
                    else:
                        # PRESERVE
                        new_images_list.append(original_img)

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
