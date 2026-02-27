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
            token_path = root_dir / ".env" / "printify_api_key.txt"
        
        if not token_path.exists():
             # Fallback: try to find it in the current working directory or standard locations
             token_path = Path(".env/printify_api_token.txt")
        if not token_path.exists():
             token_path = Path(".env/printify_api_key.txt")
        
        if not token_path.exists():
            raise FileNotFoundError(f"EARTH_BREACH: Token not found at {token_path}")
            
        return token_path.read_text().strip()

    def get_product(self, product_id: str) -> Dict[str, Any]:
        """Retrieves a specific product to use as a template."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def upload_image(self, image_url: str = None, file_name: str = "fabricated_specimen.png", local_path: str = None) -> str:
        """
        Uploads an image via URL or local file to Printify Media Library.
        Returns the new image ID.
        """
        url = f"{self.BASE_URL}/uploads/images.json"
        
        if local_path:
            import base64
            with open(local_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode("utf-8")
            payload = {
                "file_name": file_name,
                "contents": encoded_string
            }
            print(f"// UPLOADING_ARTIFACT_LOCAL: {local_path}")
        elif image_url:
            payload = {
                "file_name": file_name,
                "url": image_url
            }
            print(f"// UPLOADING_ARTIFACT_URL: {image_url}")
        else:
            raise ValueError("Must provide either image_url or local_path")
            
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        print(f"// ARTIFACT_SECURED: ID {data['id']}")
        return data['id']

    def get_templates(self) -> list:
        """Retrieves all products that are marked as templates."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products.json"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        products = response.json().get('data', [])
        templates = [p for p in products if p.get('title', '').startswith('[TEMPLATE]:')]
        return templates

    def fabricate_from_template(self, template_id: str, graphics_dir: str = "artifacts/graphics") -> Dict[str, Any]:
        """
        Clones a template product and replaces its graphics with random ones from the graphics directory.
        Maps tiles to tiled body, textures to trim, logos to logo.
        """
        import random
        
        print(f"--- [FABRICATION_START]: TEMPLATE_{template_id} ---")
        
        # 1. Get Source
        source = self.get_product(template_id)
        
        # 2. Analyze Source Images and Map to Roles
        image_roles = {} # original_id -> role ('tile', 'texture', 'logo')
        
        for area in source.get('print_areas', []):
            for ph in area.get('placeholders', []):
                pos = ph.get('position', '').lower()
                is_trim_area = 'waistband' in pos or 'trim' in pos or 'collar' in pos or 'cuff' in pos
                
                for img in ph.get('images', []):
                    img_id = img['id']
                    if img_id in image_roles:
                        continue
                    
                    # Determine role
                    if 'pattern' in img:
                        image_roles[img_id] = 'tile'
                    elif is_trim_area:
                        image_roles[img_id] = 'texture'
                    elif img.get('scale', 1) < 0.4:
                        image_roles[img_id] = 'logo'
                    else:
                        image_roles[img_id] = 'texture'
                        
        print(f"// IDENTIFIED_ROLES: {image_roles}")
        
        # 3. Pick Random Graphics for Each Role
        graphics_path = Path(graphics_dir)
        role_to_new_image_id = {}
        chosen_prompts = []
        
        for original_id, role in image_roles.items():
            # Pick a random image from the corresponding folder
            folder_name = role + "s" # tiles, textures, logos
            folder_path = graphics_path / folder_name
            
            if not folder_path.exists():
                print(f"!! [WARNING]: Folder {folder_path} does not exist. Skipping replacement for {original_id}.")
                continue
                
            # Get all images in the folder (including subdirectories)
            images = []
            for ext in ('*.png', '*.jpg', '*.jpeg'):
                images.extend(folder_path.rglob(ext))
                
            if not images:
                print(f"!! [WARNING]: No images found in {folder_path}. Skipping replacement for {original_id}.")
                continue
                
            chosen_image = random.choice(images)
            print(f"// SELECTED_ARTIFACT for {role}: {chosen_image.name}")
            
            # Try to read prompt.txt
            prompt_file = chosen_image.parent / "prompt.txt"
            if prompt_file.exists():
                try:
                    content = prompt_file.read_text()
                    for line in content.splitlines():
                        if line.startswith("prompt:"):
                            chosen_prompts.append(line.replace("prompt:", "").strip())
                            break
                except Exception:
                    pass
            
            # Upload the chosen image
            new_image_id = self.upload_image(local_path=str(chosen_image), file_name=f"fabricated_{role}_{chosen_image.name}")
            role_to_new_image_id[original_id] = new_image_id
            
        # 4. Construct Payload
        print_areas = source.get('print_areas', [])
        new_print_areas = []

        for area in print_areas:
            new_placeholders = []
            for placeholder in area.get('placeholders', []):
                images = placeholder.get('images', [])
                if not images:
                    continue
                
                new_images_list = []
                for img in images:
                    original_id = img.get('id')
                    replacement_id = role_to_new_image_id.get(original_id)
                    
                    if replacement_id:
                        new_base_obj = {
                            "id": replacement_id,
                            "x": img.get('x', 0.5),
                            "y": img.get('y', 0.5),
                            "scale": img.get('scale', 1),
                            "angle": img.get('angle', 0)
                        }
                        if 'pattern' in img:
                            new_base_obj['pattern'] = img['pattern']
                        if 'height' in img:
                            new_base_obj['height'] = img['height']
                        if 'width' in img:
                            new_base_obj['width'] = img['width']
                        new_images_list.append(new_base_obj)
                    else:
                        new_images_list.append(img)

                new_placeholders.append({
                    "position": placeholder.get('position'),
                    "images": new_images_list
                })
            
            new_print_areas.append({
                "variant_ids": area.get('variant_ids'),
                "placeholders": new_placeholders,
                "background": area.get('background')
            })

        variants = []
        for v in source.get('variants', []):
            if v.get('is_enabled', True):
                variants.append({"id": v['id'], "price": v['price'], "is_enabled": True})

        # Generate a new title
        base_title = source.get('title', '').replace('[TEMPLATE]: ', '').strip()
        new_title = f"CBG Studio | {base_title} - Fabricated"
        
        if chosen_prompts:
            try:
                from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data
                loom_model = initialize_loom_uplink()
                if loom_model:
                    prompts_str = " | ".join(chosen_prompts)
                    sys_prompt = f"You are a naming assistant for Chaya Berry Goose (CBG), an Industrial Noir/Tech-Wear brand. Generate a product name for a '{base_title}'. The design incorporates the following visual elements: {prompts_str}. Keep the name concise, clinical, and high-fidelity (e.g., 'Obsidian ISO AOP Shirt', 'Sanctuary Schematic Hoodie'). Return ONLY the name, nothing else. Do not use quotes."
                    generated_name = generate_specimen_data(loom_model, sys_prompt).strip().strip('"').strip("'")
                    if generated_name and not generated_name.startswith("["):
                        new_title = f"CBG Studio | {generated_name}"
            except Exception as e:
                print(f"!! [WARNING]: Failed to generate title with Gemini: {e}")

        if len(new_title) > 100:
            new_title = new_title[:97] + "..."

        # Append prompts to description
        new_description = source.get('description', '')
        if chosen_prompts:
            new_description += "\n\n<h3>Synthesis Directives:</h3>\n<ul>\n"
            for prompt in chosen_prompts:
                new_description += f"<li>{prompt}</li>\n"
            new_description += "</ul>"

        payload = {
            "title": new_title,
            "description": new_description,
            "blueprint_id": source.get('blueprint_id'),
            "print_provider_id": source.get('print_provider_id'),
            "variants": variants,
            "print_areas": new_print_areas
        }
        
        # 5. Create Product
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

    def clone_product(self, source_product_id: str, new_image_url: str = None, title_suffix: str = " [CLONE]", preserve_logo_only: bool = False, logo_id: str = None, trim_image_url: str = None, new_image_local_path: str = None, trim_image_local_path: str = None) -> Dict[str, Any]:
        """
        Clones a product's positioning but swaps the image.
        
        Args:
            source_product_id: ID of the product to copy.
            new_image_url: URL of the new texture/swatch (Body).
            title_suffix: String to append to the new title.
            preserve_logo_only: If True, operates in aggressive mode replacing everything except logo_id.
            logo_id: The specific image ID to treat as the protected logo.
            trim_image_url: [OPTIONAL] URL of a second texture for trim (cuffs, waistband, etc.).
            new_image_local_path: [OPTIONAL] Local path to the new texture/swatch (Body).
            trim_image_local_path: [OPTIONAL] Local path to the trim texture.
        """
        print(f"--- [FABRICATION_START]: SOURCE_{source_product_id} ---")
        
        # 1. Get Source
        source = self.get_product(source_product_id)
        
        # 2. Upload Artifacts
        new_image_id = self.upload_image(image_url=new_image_url, file_name="fabricated_body.png", local_path=new_image_local_path)
        trim_image_id = None
        if trim_image_url or trim_image_local_path:
            trim_image_id = self.upload_image(image_url=trim_image_url, file_name="fabricated_trim.png", local_path=trim_image_local_path)
            print(f"// SECONDARY_ARTIFACT_SECURED: TRIM_ID_{trim_image_id}")
        
        # [PROTOCOL_UPDATE]: Genetic Marker Logic (Universal Scanner)
        source_main_id = None
        
        # Identification Logic: Scan ALL areas to find the most frequent Image ID (The Dominant Gene)
        # We also need to consider the z-index (layer order). The base fabric is usually the first image (index 0)
        # or the one that appears in the most placeholders.
        image_frequency = {}
        base_layer_candidates = {}
        
        for area in source.get('print_areas', []):
            for ph in area.get('placeholders', []):
                images = ph.get('images', [])
                if not images:
                    continue
                
                # Track frequency of all images
                for img in images:
                    img_id = img['id']
                    image_frequency[img_id] = image_frequency.get(img_id, 0) + 1
                
                # Track the first image in each placeholder as a strong candidate for base fabric
                # BUT only if it's a main body part (not just a waistband or trim)
                pos = ph.get('position', '').lower()
                if 'waistband' not in pos and 'trim' not in pos and 'collar' not in pos:
                    # If there are multiple full-coverage layers, the user might have left an old one underneath.
                    # We should probably consider the TOP-MOST full-coverage layer as the intended base, 
                    # or just replace ALL full-coverage layers.
                    # For now, let's track all images in the main body parts to find the most frequent one.
                    for img in images:
                        img_id = img['id']
                        base_layer_candidates[img_id] = base_layer_candidates.get(img_id, 0) + 1
        
        # The ID with the highest frequency among base layer candidates is the most likely main body fabric
        if base_layer_candidates:
             source_main_id = max(base_layer_candidates, key=base_layer_candidates.get)
        elif image_frequency:
             source_main_id = max(image_frequency, key=image_frequency.get)
        
        print(f"// GENETIC_MARKER_IDENTIFIED: MAIN_ID_{source_main_id} (Frequency: {base_layer_candidates.get(source_main_id, image_frequency.get(source_main_id, 0))})")
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
                
                pos = placeholder.get('position', '').lower()
                is_trim_area = 'waistband' in pos or 'trim' in pos or 'collar' in pos
                
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
                        # If it's the main ID, replace it.
                        # If it's a full-coverage layer (scale > 0.4) in a main body part, replace it too, 
                        # to handle cases where there are hidden layers underneath.
                        is_full_coverage = original_img.get('scale', 0) > 0.4
                        
                        if original_id == source_main_id:
                            # Main Body -> New Body Texture
                            replacement_id = new_image_id
                        elif is_full_coverage and not is_trim_area:
                            # Replace any full-coverage layer in a main body part
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
                        if 'height' in original_img:
                            new_base_obj['height'] = original_img['height']
                        if 'width' in original_img:
                            new_base_obj['width'] = original_img['width']
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

        new_title = source.get('title') + title_suffix
        if len(new_title) > 100:
            new_title = new_title[:97] + "..."

        payload = {
            "title": new_title,
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
