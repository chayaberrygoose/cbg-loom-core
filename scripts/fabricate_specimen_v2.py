# [FILE_ID]: scripts/FABRICATE_SPECIMEN_V2 // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: AGILE_NANOBANANA_FABRICATION_PROTOCOL

import sys
import os
import argparse
import random
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

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
    # We'll fetch the full product to see what roles it usually needs
    source = fab.get_product(template['id'])
    
    # Simple strategy: Identify if it needs a 'tile' or 'texture' or 'logo'
    # Based on standard CBG templates, we usually have:
    # - A primary print area that needs a 'tile'
    # - Optional trim areas that need 'texture'
    # - Optional 'logo' area
    
    # For this agile script, we will generate a 'tile' and a 'texture' for every run
    # to ensure the Fabricator's 'latest' logic picks them up correctly.
    
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
    # The fabricator will handle the clinical uploading process.
    print("[SYSTEM_LOG]: Preparing artifact mapping for the Fabricator...")
    for role, path in artifact_paths.items():
        # Logic to map 'tiles' to 'tile' and 'textures' to 'texture'
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
        print(f"\n--- [FABRICATION_COMPLETE] ---")
        print(f"SPECIMEN: {product.get('title')}")
        print(f"CONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product.get('id')}")
        return product
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Realization failed: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBG Agile Specimen Fabrication Protocol")
    parser.add_argument("--theme", type=str, required=True, help="Theme for Nanobanana synthesis (e.g., 'Cyberpunk', 'Bio-Digital')")
    parser.add_argument("--template", type=str, help="Search string for target template (e.g., 'Skirt', 'Hoodie')")
    parser.add_argument("--prompt", type=str, help="Optional manual prompt override")
    
    args = parser.parse_args()
    
    fabricate_specimen(args.theme, template_search=args.template, prompt_override=args.prompt)
