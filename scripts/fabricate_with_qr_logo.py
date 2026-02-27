# [FILE_ID]: scripts/FABRICATE_QR_UPLINK // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Fabricating new Specimens using the Repository Portal QR code as the primary clinical stamp.

import sys
import requests
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from agents.skills.fabricator.fabricator import Fabricator
import random

class QRFabricator(Fabricator):
    def fabricate_fixed_logo(self, template_id: str, logo_filename: str = "repo_portal_qr.png"):
        """
        Modified fabrication that forces a specific logo while keeping other roles random.
        """
        print(f"--- [QR_FABRICATION_START]: TEMPLATE_{template_id} ---")
        
        # 1. Get Source
        source = self.get_product(template_id)
        
        # 2. Analyze Source Images and Map to Roles
        image_roles = {}
        for area in source.get('print_areas', []):
            for ph in area.get('placeholders', []):
                pos = ph.get('position', '').lower()
                is_trim_area = 'waistband' in pos or 'trim' in pos or 'collar' in pos or 'cuff' in pos
                for img in ph.get('images', []):
                    img_id = img['id']
                    if img_id in image_roles: continue
                    if 'pattern' in img: image_roles[img_id] = 'tile'
                    elif is_trim_area: image_roles[img_id] = 'texture'
                    elif img.get('scale', 1) < 0.4: image_roles[img_id] = 'logo'
                    else: image_roles[img_id] = 'texture'

        # 3. Pick Graphics
        graphics_path = Path("artifacts/graphics")
        role_to_new_image_id = {}
        chosen_prompts = []
        
        qr_logo_path = graphics_path / "logos" / logo_filename
        if not qr_logo_path.exists():
            print(f"!! [FAILURE]: QR logo not found at {qr_logo_path}")
            return

        for original_id, role in image_roles.items():
            if role == 'logo':
                chosen_image = qr_logo_path
                print(f"// FORCING_QR_LOGO: {chosen_image.name}")
            else:
                folder_path = graphics_path / (role + "s")
                images = []
                for ext in ('*.png', '*.jpg', '*.jpeg'):
                    images.extend(folder_path.rglob(ext))
                if not images:
                    print(f"!! [WARNING]: No images for {role}. Skipping.")
                    continue
                chosen_image = random.choice(images)
                print(f"// SELECTED_ARTIFACT for {role}: {chosen_image.name}")

            # Upload and map
            new_image_id = self.upload_image(local_path=str(chosen_image), file_name=f"qr_specimen_{role}_{chosen_image.name}")
            role_to_new_image_id[original_id] = new_image_id
            
            prompt = self._get_prompt_from_path(str(chosen_image))
            if prompt: chosen_prompts.append(prompt)

        # 4. Construct Payload (simplified from fabricator.py logic)
        new_print_areas = []
        for area in source.get('print_areas', []):
            new_placeholders = []
            for placeholder in area.get('placeholders', []):
                new_images_list = []
                for img in placeholder.get('images', []):
                    replacement_id = role_to_new_image_id.get(img.get('id'))
                    if replacement_id:
                        new_base = {k: v for k, v in img.items() if k in ['x', 'y', 'scale', 'angle', 'pattern', 'height', 'width']}
                        new_base['id'] = replacement_id
                        new_images_list.append(new_base)
                    else:
                        new_images_list.append(img)
                
                if new_images_list:
                    new_placeholders.append({"position": placeholder.get('position'), "images": new_images_list})
            
            if new_placeholders:
                new_print_areas.append({"variant_ids": area.get('variant_ids'), "placeholders": new_placeholders, "background": area.get('background')})

        variants = [{"id": v['id'], "price": v['price'], "is_enabled": True} for v in source.get('variants', []) if v.get('is_enabled', True)]
        
        base_title = source.get('title', '').replace('[TEMPLATE]: ', '').strip()
        new_title = f"CBG Studio | {base_title} - QR Portal Edition"

        payload = {
            "title": new_title,
            "description": source.get('description', '') + "\n\n[SYSTEM_LOG]: This specimen features the Repository Portal QR code for high-fidelity access to source protocols.",
            "blueprint_id": source.get('blueprint_id'),
            "print_provider_id": source.get('print_provider_id'),
            "variants": variants,
            "print_areas": new_print_areas
        }
        
        response = requests.post(f"{self.BASE_URL}/shops/{self.shop_id}/products.json", json=payload, headers=self.headers)
        if response.status_code != 200:
            print(f"!! [SYSTEM_FAILURE]: {response.text}")
        response.raise_for_status()
        print(f"--- [FABRICATION_COMPLETE]: {new_title} ---")
        return response.json()

def main():
    fab = QRFabricator()
    templates = fab.get_templates()
    
    # Pick a few diverse templates
    target_templates = [
        "Unisex Cut & Sew Tee",
        "Unisex Pullover Hoodie",
        "High Waisted Yoga Leggings"
    ]
    
    for tt in target_templates:
        template = next((t for t in templates if tt in t['title']), None)
        if template:
            try:
                fab.fabricate_fixed_logo(template['id'])
            except Exception as e:
                print(f"!! [ERROR] Failed to fabricate {tt}: {e}")

if __name__ == "__main__":
    main()
