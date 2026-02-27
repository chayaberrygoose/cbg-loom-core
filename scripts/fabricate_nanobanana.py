# [FILE_ID]: scripts/FABRICATE_NANOBANANA // VERSION: 1.0 // STATUS: STABLE
# [SYSTEM_LOG]: INTEGRATING_NANOBANANA_WITH_THE_FABRICATOR

import sys
import os
import random
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image
from agents.skills.fabricator.fabricator import Fabricator

def get_nanobanana_prompt():
    """
    Generates a prompt based on CBG Industrial Noir/Sub-Atomic lore.
    """
    themes = [
        "Industrial Noir", "Cyber-Punk", "Sub-Atomic", "Bio-Digital", 
        "Data-Stream", "Phonon-Lattice", "Quantum-Etch"
    ]
    elements = [
        "phosphor green circuitry", "deep obsidian textures", "glitch-offset Goose icons", 
        "translucent berry-red data streams", "anodized aluminum panels", "neon-etched sigils",
        "liquid nitrogen vapor", "chromatic aberration patterns"
    ]
    composition = [
        "hyper-detailed macro photography", "4k isometric render", "schematic blueprint aesthetic",
        "minimalist vector lines", "orthographic projection", "high-fidelity texture map"
    ]
    
    theme = random.choice(themes)
    el1 = random.choice(elements)
    el2 = random.choice(elements)
    comp = random.choice(composition)
    
    prompt = f"CBG Studio Style: {theme} aesthetics, featuring {el1} and {el2}, {comp}, high contrast, sharp details, industrial noir color palette."
    return prompt

def main():
    load_dotenv()
    fab = Fabricator()
    
    print("[SYSTEM_LOG]: Initializing Nanobanana Fabrication Pipeline...")
    
    # 1. Fetch Templates
    templates = fab.get_templates()
    if not templates:
        print("[SYSTEM_ERROR]: No active templates found in the Archive.")
        return
    
    # Select a target template (or loop through them)
    # For this ritual, we pick one randomly or take the first one
    template = random.choice(templates)
    print(f"[SYSTEM_LOG]: Target Specimen Template: {template['title']}")
    
    # 2. Synthesize Visual Specimens
    artifact_dir = Path("artifacts/specimens/nanobanana")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    specimens = []
    # We'll generate 2 variations: one for the 'tile' and one for the 'texture'
    roles = ['tile', 'texture']
    
    for role in roles:
        prompt = get_nanobanana_prompt()
        print(f"[SIGNAL_BROADCAST]: Requesting {role} synthesis from Nanobanana...")
        
        # Now using the updated routing logic
        result_path = generate_nano_banana_image(prompt, graphic_type_override=role if role == "tiles" else "textures")
        
        if result_path:
            specimens.append({"path": result_path, "role": role})
        else:
            print(f"[SYSTEM_ERROR]: {role} synthesis failed.")

    if len(specimens) < 1:
        print("[SYSTEM_ERROR]: Insufficient artifacts synthesized for fabrication.")
        return

    # 3. Upload and Fabricate
    print("[SYSTEM_LOG]: Uploading artifacts to the Conduit...")
    
    image_ids = {}
    for spec in specimens:
        image_id = fab.upload_image(local_path=spec['path'], file_name=os.path.basename(spec['path']))
        image_ids[spec['role']] = image_id

    # 4. Clone and Realize Product
    print("[SYSTEM_LOG]: Realizing new Specimen in the Printify Archive...")
    
    # We use a simplified override structure. 
    # The fabricator's decorate_from_template usually picks latest, but we can pass explicit mapping if we modify it.
    # For now, we'll try to use the latest since our upload just happened.
    
    try:
        # We'll just call the standard fabrication which picks up the latest graphics
        # If the fabricator is set to look at specific directories, we might need to point it there.
        # But looking at fabricator.py, it seems it handles overrides via role_overrides if passed.
        
        # NOTE: fabricate_from_template logic in fabricator.py (from context) uses role_overrides 
        # but let's see if we can just rely on the latest uploads.
        product = fab.fabricate_from_template(template['id'])
        print(f"[SYSTEM_SUCCESS]: Specimen realized: {product.get('title', 'Unknown')}")
        print(f"[SYSTEM_LOG]: Conduit Link: https://printify.com/app/store/{fab.shop_id}/products/{product.get('id')}")
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Fabrication failed: {e}")

if __name__ == "__main__":
    main()
