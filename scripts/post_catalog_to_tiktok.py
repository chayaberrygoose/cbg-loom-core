# [FILE_ID]: scripts/POST_CATALOG_TO_TIKTOK // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Automating the pipeline from Printify Catalog to TikTok Evidence.

import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing skills
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from agents.skills.tiktok_skill.tiktok_skill import TikTokConduit
from agents.skills.tiktok_skill.synthesizer import synthesize_video_from_image

def main():
    if len(sys.argv) < 2:
        print("[SYSTEM_USAGE]: python3 scripts/post_catalog_to_tiktok.py <image_filename_or_path>")
        return

    target = sys.argv[1]
    
    # Resolve target image path
    image_path = Path(target)
    if not image_path.exists():
        # Try finding it in artifacts/catalog/Product images
        catalog_dir = project_root / "artifacts" / "catalog" / "Product images"
        image_path = catalog_dir / target
        
        if not image_path.exists():
            # Try appending extension if missing
            if not target.endswith(".jpg"):
                image_path = catalog_dir / f"{target}_0.jpg"

    if not image_path.exists():
        print(f"[SYSTEM_DISSONANCE]: Cannot locate Specimen: {target}")
        return

    print(f"[SYSTEM_LOG]: Target Specimen identified: {image_path.name}")
    
    # 1. Synthesize Video
    video_path = synthesize_video_from_image(image_path)
    if not video_path:
        return

    # 2. Upload to TikTok
    print("--- [UPLOAD_RITUAL]: INITIATING ---")
    conduit = TikTokConduit()
    title = f"CBG Studio // {image_path.stem.replace('_', ' ')}"
    
    result = conduit.post_video(video_path, title=title)
    
    if result:
        print(f"--- [RITUAL_COMPLETE]: SUCCESS ---")
        print(f"Publish ID: {result}")
    else:
        print(f"--- [RITUAL_COMPLETE]: FAILED ---")

if __name__ == "__main__":
    main()
