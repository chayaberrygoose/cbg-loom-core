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
    
    # Pick a random template
    template = random.choice(templates)
    print(f"Selected template: {template['title']} ({template['id']})")
    
    # Fabricate
    try:
        fab.fabricate_from_template(template['id'])
        print("Fabrication successful!")
    except Exception as e:
        print(f"Fabrication failed: {e}")

if __name__ == "__main__":
    main()
