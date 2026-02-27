# [FILE_ID]: scripts/FABRICATE_SPECIMEN_V2 // VERSION: 1.1 // STATUS: STABLE
# [SYSTEM_LOG]: AGILE_NANOBANANA_FABRICATION_PROTOCOL_V2

import sys
import os
import argparse
import random
import time
import requests
import io
import json
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image
from agents.skills.fabricator.fabricator import Fabricator

def generate_context_prompt(theme, role, base_prompt=None):
    """
    Synthesizes a role-specific Nanobanana prompt based on the target theme.
    """
    if base_prompt:
        return f"CBG Studio | {theme} Style: {base_prompt}"
    
    role_modifiers = {
        "tile": "seamless textile pattern, repeatable surface design, flat layout, architectural motif",
        "texture": "macro material detail, industrial surface texture, weathered finish, high-fidelity map",
        "logo": "minimalist vector icon, clinical stamp, high-contrast sigil, white or black background",
        "standalone": "high-fidelity 4k render, industrial noir aesthetic, cinematic lighting, sharp detail"
    }
    
    modifier = role_modifiers.get(role, role_modifiers["standalone"])
    
    return f"CBG Studio | {theme} Aesthetics: {modifier}, industrial noir color palette, phosphor green accents, sharp details, high contrast."

def synthesize_lifestyle_mockup(theme, product_title, mockup_url, style_ref_dir="artifacts/Lifestyle Photo Reference"):
    """
    Synthesizes a lifestyle image for the product by using the Printify mockup as a base
    and applying Nanobanana's vision guided by the lifestyle reference photos.
    """
    print(f"[SIGNAL_BROADCAST]: Synthesizing Lifestyle Mockup for {product_title}...")
    
    # 1. Fetch the mockup image data
    image_context = None
    try:
        resp = requests.get(mockup_url)
        resp.raise_for_status()
        image_context = Image.open(io.BytesIO(resp.content))
        print(f"✅ [SYSTEM_LOG]: Mockup context secured for Nanobanana synthesis.")
    except Exception as e:
        print(f"⚠️ [SYSTEM_WARNING]: Failed to fetch mockup image for context: {e}")

    # Identify a style reference
    ref_dir = Path(style_ref_dir)
    refs = list(ref_dir.glob("*.PNG")) + list(ref_dir.glob("*.png"))
    chosen_ref = random.choice(refs) if refs else None
    
    # Prompt logic
    ref_desc = "industrial noir techwear aesthetic, high-contrast shadows, clinical warehouse lighting"
    prompt = (
        f"CBG Studio | Lifestyle Realization: A high-fidelity lifestyle photo. "
        f"The subject is the specific apparel product shown in the provided image. "
        f"CRITICAL: The product in the new photo must be EXACTLY identical to the base image. "
        f"You must replicate the pattern, colors, and placement with 100% precision. "
        f"Context: {theme} style. Visual Reference Style: {ref_desc}. "
        f"The shot should be a medium close-up, focusing on the quality and design of the product specimen."
    )
    
    # Routing to standalone artifacts
    output_path = generate_nano_banana_image(
        prompt, 
        graphic_type_override="mockups",
        image_context=image_context
    )
    return output_path

def fabricate_specimen(theme, template_search=None, prompt_override=None):
    load_dotenv()
    fab = Fabricator()
    
    print(f"[SYSTEM_LOG]: Initializing Fabrication Ritual for Theme: {theme}")
    
    # 1. Resolve Template
    templates = fab.get_templates()
    if template_search:
        target_templates = [t for t in templates if template_search.lower() in t['title'].lower()]
        if not target_templates:
            print(f"[SYSTEM_WARNING]: No template matching '{template_search}' found. Selecting random.")
            template = random.choice(templates)
        else:
            template = random.choice(target_templates)
    else:
        template = random.choice(templates)
    
    print(f"[SYSTEM_LOG]: Selected Template: {template['title']} (ID: {template['id']})")
    
    # 2. Analyze Roles for the Template
    source = fab.get_product(template['id'])
    
    roles_to_generate = ["tiles", "textures"]
    artifact_paths = {}

    for role in roles_to_generate:
        prompt = generate_context_prompt(theme, role[:-1], base_prompt=prompt_override)
        print(f"[SIGNAL_BROADCAST]: Requesting '{role}' synthesis for theme '{theme}'...")
        
        # This will use the updated nanobanana_skill routing to artifacts/graphics/<role>/...
        result_path = generate_nano_banana_image(prompt, graphic_type_override=role)
        
        if result_path:
            artifact_paths[role] = result_path
            print(f"✅ [SYSTEM_LOG]: Artifact secured: {result_path}")
        else:
            print(f"❌ [SYSTEM_ERROR]: Failed to synthesize {role}")

    if not artifact_paths:
        print("[SYSTEM_ERROR]: No artifacts stabilized. Aborting ritual.")
        return

    # Identifiers for the fabricator
    role_overrides = {}
    
    # We'll pass the local paths to the fabricator via role_overrides.
    print("[SYSTEM_LOG]: Preparing artifact mapping for the Fabricator...")
    for role, path in artifact_paths.items():
        role_type = "tile" if role == "tiles" else "texture"
        role_overrides[role_type] = path

    # 3. Realize Product
    print("[SYSTEM_LOG]: Realizing specimen...")
    
    try:
        # Use fabricate_from_template which handles the cloning and role mapping
        product = fab.fabricate_from_template(
            template['id'], 
            role_overrides=role_overrides
        )
        product_id = product.get('id')
        product_title = product.get('title')
        print(f"\n--- [FABRICATION_COMPLETE]: ID_{product_id} ---")
        print(f"SPECIMEN: {product_title}")
        
        # 4. Lifestyle Realization Step
        print("[SYSTEM_LOG]: Protocol Initiation: LIFESTYLE_REALIZATION")
        
        # We need to RE-FETCH the product to get the mockups generated by Printify after cloning
        time.sleep(5)  # Brief pause for Printify to initialize the specimen
        product = fab.get_product(product_id)
        images = product.get('images', [])
        
        if images:
            # Look for 'front' mockup specifically if possible, else default to first
            mockup_url = images[0].get('src')
            for img in images:
                if 'front' in img.get('variant_ids', []) or 'front' in img.get('src', '').lower():
                    mockup_url = img.get('src')
                    break
                    
            lifestyle_path = synthesize_lifestyle_mockup(theme, product_title, mockup_url)
            
            if lifestyle_path:
                print(f"[SYSTEM_LOG]: Lifestyle artifact stabilized. Injecting into Conduit...")
                # Ensure the file exists before upload
                if os.path.exists(lifestyle_path):
                    # [SIGNAL_RECOVERY]: Re-check file integrity and ensure binary read if needed
                    file_size = os.path.getsize(lifestyle_path)
                    print(f"// UPLOADING_LIFESTYLE: {lifestyle_path} ({file_size} bytes)")
                    
                    # Printify upload ritual
                    lifestyle_media_id = fab.upload_image(local_path=lifestyle_path, file_name=f"lifestyle_{product_id}.png")
                    
                    if lifestyle_media_id:
                        print(f"// ARTIFACT_SECURED: ID_{lifestyle_media_id}. Waiting for Conduit sync...")
                        # Increase wait time for the Printify media library to process the image before injection
                        time.sleep(10)
                        
                        # [NEW_PROTOCOL]: Injecting into description as gallery upload is restricted for external images
                        fab.add_lifestyle_to_description(product_id, lifestyle_media_id)
                        print(f"✅ [SYSTEM_SUCCESS]: Lifestyle mockup realized and injected into {product_id} description.")
                        
                        # [LINKAGE_STAMP]: Archive the relationship between Printify Product and Lifestyle Specimen
                        mapping_file = Path(lifestyle_path).parent / "product_link.json"
                        link_data = {
                            "product_id": product_id,
                            "product_title": product_title,
                            "conduit_url": f"https://printify.com/app/store/{fab.shop_id}/products/{product_id}",
                            "lifestyle_media_id": lifestyle_media_id,
                            "lifestyle_local_path": lifestyle_path,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        }
                        mapping_file.write_text(json.dumps(link_data, indent=4))
                        print(f"✅ [SYSTEM_LOG]: Linkage secured: {mapping_file}")
                    else:
                        print(f"❌ [SYSTEM_ERROR]: Media upload failed to return ID.")
                else:
                    print(f"❌ [SYSTEM_ERROR]: Lifestyle path {lifestyle_path} not found.")
        
        print(f"CONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product_id}")
        return product
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Realization failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBG Agile Specimen Fabrication Protocol")
    parser.add_argument("--theme", type=str, required=True, help="Theme for Nanobanana synthesis")
    parser.add_argument("--template", type=str, help="Search string for target template")
    parser.add_argument("--prompt", type=str, help="Optional manual prompt override")
    
    args = parser.parse_args()
    
    fabricate_specimen(args.theme, template_search=args.template, prompt_override=args.prompt)
