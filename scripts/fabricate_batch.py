import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from agents.skills.fabricator.fabricator import Fabricator
import random

def main():
    fab = Fabricator()
    
    print("Fetching templates...")
    templates = fab.get_templates()
    
    if not templates:
        print("No templates found. Make sure products start with '[TEMPLATE]: '")
        return
        
    print(f"Found {len(templates)} templates.")
    
    # Find the shorts template
    shorts_template = next((t for t in templates if "Shorts" in t['title']), None)
    
    if not shorts_template:
        print("Could not find a template for Shorts.")
        return
        
    print(f"Selected template: {shorts_template['title']} ({shorts_template['id']})")
    
    # Fabricate 5 times
    for i in range(5):
        print(f"\n--- Fabricating Short {i+1}/5 ---")
        try:
            fab.fabricate_from_template(shorts_template['id'])
            print(f"Fabrication {i+1} successful!")
        except Exception as e:
            print(f"Fabrication {i+1} failed: {e}")

if __name__ == "__main__":
    main()
