"""
/* [FILE_ID]: FABRICATOR // VERSION: 1.0 // STATUS: UNSTABLE */
This module handles the cloning of Printify products with new swatches.
"""

import os
import json
import requests
import time
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
        self.last_upload_src = None

    def _load_token(self) -> str:
        """Loads the Printify API token from the environment file or environment variables."""
        from dotenv import load_dotenv
        load_dotenv()
        
        token = os.getenv("printify_api_key") or os.getenv("PRINTIFY_API_KEY") or os.getenv("printify_api_token")
        if token:
            return token

        # Fallback to legacy file-based loading
        current_file = Path(__file__)
        root_dir = current_file.parent.parent.parent.parent
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
        
        # [SIGNAL_RECOVERY]: Handle potential transient 500s or out-of-sync template refs
        response = requests.get(url, headers=self.headers)
        if response.status_code == 500:
            print(f"!! [SYSTEM_WARPING]: 500 Server Error for Product {product_id}. Retrying handshake...")
            time.sleep(2)
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
            
        # [SIGNAL_RECOVERY]: Handle transient 500/502/504 during file upload
        max_retries = 3
        for attempt in range(max_retries):
            response = requests.post(url, json=payload, headers=self.headers)
            if response.status_code in [500, 502, 503, 504]:
                print(f"!! [SIGNAL_WARPING]: {response.status_code} Error. Attempt {attempt+1}/{max_retries}. Retrying in 5s...")
                time.sleep(5)
                continue
            break

        response.raise_for_status()
        data = response.json()
        print(f"// ARTIFACT_SECURED: ID {data['id']}")
        
        # [PROTOCOL_UPDATE]: Capture the source URL for immediate injection
        # Printify returns 'preview_url' for uploads, not 'src'
        self.last_upload_src = data.get('preview_url') or data.get('src')
        print(f"// UPLOAD_SRC_RESOLVED: {self.last_upload_src}")
        
        return data['id']

    def get_templates(self) -> list:
        """Retrieves all products that are marked as templates."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products.json"
        
        # [SIGNAL_RECOVERY]: Handle transient 500/502/504
        for attempt in range(3):
            response = requests.get(url, headers=self.headers)
            if response.status_code >= 500:
                print(f"!! [SIGNAL_WARPING]: {response.status_code} Error on Template Fetch. Retrying...")
                time.sleep(5)
                continue
            break
            
        response.raise_for_status()
        products = response.json().get('data', [])
        templates = [p for p in products if p.get('title', '').startswith('[TEMPLATE]:')]
        return templates

    def _get_prompt_from_path(self, local_path: str) -> Optional[str]:
        """Looks for a prompt.txt file adjacent to the provided image path."""
        if not local_path:
            return None
        
        path = Path(local_path)
        prompt_file = path.parent / "prompt.txt"
        if prompt_file.exists():
            try:
                content = prompt_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.strip().startswith("prompt:"):
                        return line.replace("prompt:", "", 1).strip()
            except Exception:
                pass
        return None

    def fabricate_from_template(self, template_id: str, graphics_dir: str = "artifacts/graphics", role_overrides: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Clones a template product and replaces its graphics with specimens from the graphics directory.
        By default, it takes the latest specimen for each role (tile, texture, logo).
        Maps tiles to tiled body, textures to trim, logos to logo.
        """
        import random
        from typing import Dict
        
        role_overrides = role_overrides or {}
        
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
        
        # 3. Secure Graphics for Each Role
        graphics_path = Path(graphics_dir)
        role_to_new_image_id = {}
        chosen_prompts = []
        
        # Cache for role consistency (one image per unique role per template)
        role_instance_map = {} # role -> (path, id)
        
        for original_id, role in image_roles.items():
            if role in role_instance_map:
                role_to_new_image_id[original_id] = role_instance_map[role][1]
                continue

            # Check for explicit override
            if role in role_overrides:
                chosen_image = Path(role_overrides[role])
                print(f"// FORCING_ARTIFACT for {role}: {chosen_image.name}")
            else:
                folder_name = role + "s" # tiles, textures, logos
                folder_path = graphics_path / folder_name
                
                if not folder_path.exists():
                    print(f"!! [WARNING]: Folder {folder_path} does not exist. Skipping.")
                    continue
                    
                # Get all images in the folder (including subdirectories)
                images = []
                for ext in ('*.png', '*.jpg', '*.jpeg'):
                    images.extend(folder_path.rglob(ext))
                    
                if not images:
                    print(f"!! [WARNING]: Folder {folder_path} exists but is void of specimens. Skipping.")
                    continue
                    
                # Sort by modification time (descending) to prioritize the latest synthesis
                images.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                chosen_image = images[0]
                print(f"// SELECTED_ARTIFACT (LATEST) for {role}: {chosen_image.name}")
            
            # Extract prompt if available
            prompt = self._get_prompt_from_path(str(chosen_image))
            if prompt:
                chosen_prompts.append(prompt)
            
            # Upload the chosen image
            new_image_id = self.upload_image(local_path=str(chosen_image), file_name=f"fabricated_{role}_{chosen_image.name}")
            role_to_new_image_id[original_id] = new_image_id
            role_instance_map[role] = (str(chosen_image), new_image_id)
            
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
        
        # [PROTOCOL_UPDATE]: Re-enabling Title Generation via Nanobanana Synthesis Logic
        if chosen_prompts:
            try:
                # Use the new prompt-based naming ritual
                from google import genai
                from google.genai import types
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("gemini_api_key")
                client = genai.Client(api_key=api_key)
                
                prompts_str = " | ".join(chosen_prompts)
                sys_prompt = f"You are a naming architect for Chaya Berry Goose (CBG), an Industrial Noir/Tech-Wear brand. Generate a product name for a '{base_title}'. Narrative Context: {prompts_str}. Requirements: Concise, clinical, high-fidelity (e.g., 'Obsidian ISO Hoodie', 'Sanctuary Schematic Joggers'). Output ONLY the name."
                
                response = client.models.generate_content(
                    model="gemini-2.5-flash", # Confirmed reachable by list_models
                    contents=sys_prompt
                )
                
                generated_name = response.text.strip().strip('"').strip("'")
                if generated_name and len(generated_name) < 50:
                    new_title = f"CBG Studio | {generated_name}"
            except Exception as e:
                print(f"!! [WARNING]: Narrative synthesis failed: {e}. Using fallback title.")

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

    def update_product(self, product_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates an existing product's metadata or configuration."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json"
        response = requests.put(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

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
        
        # Extract prompts if available
        cloned_prompts = []
        body_prompt = self._get_prompt_from_path(new_image_local_path)
        if body_prompt:
             cloned_prompts.append(body_prompt)
        trim_prompt = self._get_prompt_from_path(trim_image_local_path)
        if trim_prompt:
             cloned_prompts.append(trim_prompt)

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

        # Append prompts to description
        new_description = source.get('description', '')
        if cloned_prompts:
            new_description += "\n\n<h3>Synthesis Directives:</h3>\n<ul>\n"
            for prompt in cloned_prompts:
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

    def update_product_description(self, product_id: str, description: str) -> Dict[str, Any]:
        """Updates the description of an existing product."""
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json"
        payload = {"description": description}
        response = requests.put(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _resolve_upload_src(self, image_id: str, max_retries: int = 3) -> Optional[str]:
        """Resolves the publicly accessible URL for an uploaded image, with retry logic."""
        # Priority 1: Cached from last upload
        if self.last_upload_src:
            return self.last_upload_src
        
        for attempt in range(max_retries):
            # Priority 2: Direct single-image endpoint
            try:
                single_url = f"{self.BASE_URL}/uploads/{image_id}.json"
                resp = requests.get(single_url, headers=self.headers)
                if resp.ok:
                    data = resp.json()
                    src = data.get('preview_url') or data.get('src')
                    if src:
                        return src
            except Exception:
                pass
            
            # Priority 3: Media library listing scan
            try:
                media_url = f"{self.BASE_URL}/uploads.json"
                media_resp = requests.get(media_url, headers=self.headers)
                if media_resp.ok:
                    for item in media_resp.json().get('data', []):
                        if item.get('id') == image_id:
                            src = item.get('preview_url') or item.get('src')
                            if src:
                                return src
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"// SIGNAL_RETRY: Attempt {attempt + 1}/{max_retries} failed. Waiting {wait}s for CDN propagation...")
                time.sleep(wait)
        
        return None

    def add_lifestyle_to_description(self, product_id: str, image_id: str, image_src: str = None) -> Dict[str, Any]:
        """
        [DEPRECATED]: Printify sanitizes <img> tags from descriptions.
        This method now only logs the lifestyle URL for reference in the description
        without injecting broken HTML.
        """
        print(f"⚠️ [PROTOCOL_NOTE]: Printify strips <img> from descriptions. Skipping HTML injection.")
        print(f"// LIFESTYLE_CDN_URL: {image_src or 'unresolved'}")
        return {}

    def add_product_image(self, product_id: str, image_src: str, image_id: str = None) -> Dict[str, Any]:
        """
        Adds an image to a product's gallery using the CDN src URL.
        Printify product images use 'src' (not media library 'id').
        """
        url = f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json"
        
        if not image_src:
            print(f"!! [SIGNAL_LOST]: No src URL provided for gallery injection. Aborting.")
            return {}
        
        source = self.get_product(product_id)
        existing_images = source.get('images', [])
        
        # Check if already added by src URL
        if any(img.get('src') == image_src for img in existing_images):
            print(f"// IMAGE_ALREADY_EXISTS: {image_src[:60]}")
            return source
            
        # Get all variant IDs
        variant_ids = [v['id'] for v in source.get('variants', []) if v.get('is_enabled', True)]
        
        # Printify product images require 'src' URL, not media library 'id'
        new_image = {
            "src": image_src,
            "variant_ids": variant_ids,
            "position": "other",
            "is_default": False,
            "is_selected_for_publishing": True
        }
        
        new_images_payload = existing_images + [new_image]
        payload = {"images": new_images_payload}
        
        print(f"// INJECTING_TO_GALLERY: {image_src[:60]}... (Total: {len(new_images_payload)})")
        response = requests.put(url, json=payload, headers=self.headers)
        
        if not response.ok:
            print(f"!! [CONDUIT_REJECTION]: {response.status_code} - {response.text[:200]}")
            response.raise_for_status()
            
        updated_product = response.json()
        
        # Verify by checking if image count increased
        final_images = updated_product.get('images', [])
        original_count = len(existing_images)
        final_count = len(final_images)
        
        # Also check by src URL match
        src_match = any(image_src in (img.get('src') or '') for img in final_images)
        
        if final_count > original_count or src_match:
            print(f"✅ [SIGNAL_CONFIRMED]: Gallery updated ({original_count} -> {final_count} images).")
            return updated_product
        else:
            print(f"⚠️ [SIGNAL_WARNING]: PUT accepted but image count unchanged ({original_count} -> {final_count}).")
            print(f"// DEBUG_SRCS: {[img.get('src', 'N/A')[:50] for img in final_images]}")
            return updated_product

if __name__ == "__main__":
    # Example Usage (Commented out to prevent accidental execution)
    # fab = Fabricator()
    # fab.clone_product("66fb...", "https://...")
    pass
