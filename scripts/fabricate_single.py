import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from agents.skills.fabricator.fabricator import Fabricator

def main():
    fab = Fabricator()
    
    print("Fetching templates...")
    templates = fab.get_templates()
    
    if not templates:
        print("No templates found. Make sure products start with '[TEMPLATE]: '")
        return
        
    # Find the Skater Skirt template
    skirt_template = next((t for t in templates if "Skater Skirt" in t['title']), None)
    
    if not skirt_template:
        print("Could not find a template for Skater Skirt.")
        return
        
    print(f"Selected template: {skirt_template['title']} ({skirt_template['id']})")
    
    print(f"\n--- Fabricating Industrial Noir Skater Skirt ---")
    try:
        # We will let the fabricator pick randomly, but since we just generated 3 new images,
        # there's a chance it picks them. To guarantee it, we could modify the fabricator,
        # but for now, let's just run it and see what we get from the pool.
        fab.fabricate_from_template(skirt_template['id'])
        print(f"Fabrication successful!")
    except Exception as e:
        print(f"Fabrication failed: {e}")

if __name__ == "__main__":
    main()
