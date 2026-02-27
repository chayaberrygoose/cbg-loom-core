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
    
    # Fabricate 5 times for each template
    for template in templates:
        print(f"\n==================================================")
        print(f"Processing Template: {template['title']} ({template['id']})")
        print(f"==================================================")
        
        for i in range(5):
            print(f"\n--- Fabricating Specimen {i+1}/5 ---")
            try:
                fab.fabricate_from_template(template['id'])
                print(f"Fabrication {i+1} successful!")
            except Exception as e:
                print(f"Fabrication {i+1} failed: {e}")

if __name__ == "__main__":
    main()
