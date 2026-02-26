"""
/* [FILE_ID]: TEST_FABRICATOR // VERSION: 1.0 // STATUS: TESTING */
Test script for the Fabricator protocol. 
"""

import os
import sys
from pathlib import Path

# Ensure we can import the module
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from agents.skills.fabricator.fabricator import Fabricator

# --- CONFIGURATION [EDIT_BEFORE_RUNNING] ---
SOURCE_PRODUCT_ID = "699abcd0c7c3be94ff0c20ad"  # Red Black Plaid Glitch Zip Hoodie
# Replace this with a valid image URL to test the cloning
NEW_IMAGE_URL = "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80" 
NEW_TITLE_SUFFIX = " // PROTOCOL_TEST_AGGRESSIVE"

# The ID of the Logo to preserve (from previous context: IMG_1936.png)
LOGO_ID = "6995fafee0068a54871a8000"
# -------------------------------------------

def run_test():
    print(f"--- [TEST_INIT]: FABRICATOR_PROTOCOL ---")
    
    try:
        fab = Fabricator()
        
        print(f"Targeting Source Product: {SOURCE_PRODUCT_ID}")
        print(f"Injecting Specimen Image: {NEW_IMAGE_URL}")
        print(f"Preserving ONLY Logo ID: {LOGO_ID}")
        
        # Execute Clone
        new_product = fab.clone_product(
            source_product_id=SOURCE_PRODUCT_ID,
            new_image_url=NEW_IMAGE_URL,
            title_suffix=NEW_TITLE_SUFFIX,
            preserve_logo_only=True,
            logo_id=LOGO_ID
        )
        
        print(f"\n[SUCCESS] New Product Fabricated!")
        print(f"ID: {new_product.get('id')}")
        print(f"Title: {new_product.get('title')}")
        print(f"External Handle: {new_product.get('external', {}).get('handle')}")
        
    except Exception as e:
        print(f"\n[FAILURE] Protocol Interrupted: {e}")

if __name__ == "__main__":
    run_test()
