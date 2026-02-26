"""
/* [FILE_ID]: INSPECT_PRODUCT // VERSION: 1.0 // STATUS: UTILITY */
Utility to inspect a product's structure and verify compatibility with Fabricator logic.
"""

import sys
from pathlib import Path
import json

# Ensure we can import the module
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from agents.skills.fabricator.fabricator import Fabricator

TARGET_ID = "69925cac064523edc10c61f6"

def inspect():
    fab = Fabricator()
    print(f"--- [INSPECTION_START]: TARGET_{TARGET_ID} ---")
    
    try:
        product = fab.get_product(TARGET_ID)
        print(f"Title: {product.get('title')}")
        print(f"Blueprint ID: {product.get('blueprint_id')}")
        
        # Simulated Genetic Marker Logic (Universal Scanner)
        source_main_id = None
        image_frequency = {}
        
        for area in product.get('print_areas', []):
            for ph in area.get('placeholders', []):
                images = ph.get('images', [])
                if not images:
                    continue
                # Assume the first image (Layer 0) is the base fabric in most cases
                base_img_id = images[0]['id']
                image_frequency[base_img_id] = image_frequency.get(base_img_id, 0) + 1
        
        if image_frequency:
             source_main_id = max(image_frequency, key=image_frequency.get)
        
        if source_main_id:
            print(f"// VERIFIED_GENETIC_MARKER: {source_main_id} (Frequency: {image_frequency.get(source_main_id)})")
        else:
            print(f"!! [WARNING]: No Genetic Marker identified. Fabricator might fail to swap texture.")

        print("\n--- [ARTIFACT_ANALYSIS] ---")
        for area in product.get('print_areas', []):
            for ph in area.get('placeholders', []):
                pos = ph['position']
                images = ph.get('images', [])
                print(f"Position: {pos}")
                for i, img in enumerate(images):
                    img_id = img.get('id')
                    role = "UNKNOWN"
                    if img_id == source_main_id:
                        role = "MAIN_BODY (Target for Replacement)"
                    else:
                        role = "DISTINCT_ARTIFACT (Trim/Logo)"
                    print(f"  - Layer {i}: ID_{img_id} [{role}]")

    except Exception as e:
        print(f"Inspection Failed: {e}")

if __name__ == "__main__":
    inspect()
