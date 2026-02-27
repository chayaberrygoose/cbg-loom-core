# [FILE_ID]: skills/NANOBANANA_SKILL // VERSION: 1.0 // STATUS: STABLE 
# [SYSTEM_LOG]: IMAGE_SYNTHESIS_SUBSYSTEM_ONLINE

import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 1. Setup Client
# Ensure your API key is in your environment variables
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("gemini_api_key")
client = genai.Client(api_key=api_key)

def _tokenize(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())

def _slugify_prompt(prompt: str, max_words: int = 8) -> str:
    words = _tokenize(prompt)
    if not words:
        return "specimen"
    return "-".join(words[:max_words])[:80].strip("-") or "specimen"

def _load_graphic_type_definitions() -> dict:
    readme_path = Path("artifacts/graphics/README.md")
    if not readme_path.exists():
        return {
            "standalone": "standalone images",
            "textures": "textures for trim or overlays",
            "tiles": "graphics meant to be tiled",
        }

    content = readme_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    definitions = {}
    current_key = None
    current_lines = []

    for line in content:
        heading_match = re.match(r"^##\s+(.+)$", line.strip(), flags=re.IGNORECASE)
        if heading_match:
            if current_key is not None:
                definitions[current_key] = " ".join(current_lines).strip()
            current_key = heading_match.group(1).strip().lower()
            current_lines = []
            continue

        if current_key is not None and line.strip():
            current_lines.append(line.strip())

    if current_key is not None:
        definitions[current_key] = " ".join(current_lines).strip()

    if not definitions:
        definitions = {"standalone": "standalone", "textures": "textures", "tiles": "tiles"}

    if "logos" in definitions:
        del definitions["logos"]

    return definitions

def _classify_graphic_type(prompt: str) -> str:
    definitions = _load_graphic_type_definitions()
    prompt_tokens = set(_tokenize(prompt))

    forced_tiles = {"tile", "tiles", "tiled", "tiling", "seamless", "repeat", "repeatable"}
    if prompt_tokens.intersection(forced_tiles):
        if "tiles" in definitions:
            return "tiles"

    if "standalone" in definitions:
        return "standalone"
    
    return list(definitions.keys())[0] if definitions else "standalone"

def generate_nano_banana_image(prompt, output_path=None, graphic_type_override=None):
    """
    Synthesizes visual specimens via the Nanobanana (Gemini 3.1 Flash Image) protocol.
    Directs output to the appropriate artifact routing directory.
    """
    print(f"🎨 [SIGNAL_BROADCAST]: Sending prompt to Nanobanana: {prompt}")
    
    # Artifact Routing
    graphic_type = graphic_type_override if graphic_type_override else _classify_graphic_type(prompt)
    root = Path("artifacts/graphics")
    type_dir = root / graphic_type
    type_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify_prompt(prompt)
    run_dir = type_dir / f"{stamp}__{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    final_output_path = Path(output_path) if output_path else run_dir / "specimen.png"
    
    try:
        # 2. Call the Model
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1"
                )
            )
        )

        # 3. Process and Save
        image_saved = False
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                img = part.as_image()
                img.save(final_output_path)
                print(f"✅ [SYSTEM_LOG]: Specimen stabilized at: {final_output_path}")
                
                # Write prompt metadata
                prompt_file = run_dir / "prompt.txt"
                prompt_file.write_text(f"prompt: {prompt}\nmodel: gemini-3.1-flash-image-preview\ntimestamp: {stamp}", encoding="utf-8")
                image_saved = True
                break
            
            if part.text:
                print(f"📝 [NANO_BANANA_LOG]: {part.text}")

        if image_saved:
            return str(final_output_path)
            
    except Exception as e:
        print(f"❌ [SYSTEM_ERROR]: Image synthesis failed: {e}")
        return None

if __name__ == "__main__":
    # Test for Chaya Berry Goose Lore
    test_prompt = "Industrial Noir style, a goose wearing a berry-patterned waistcoat, standing in a neon-lit library, high-fidelity 4k render, phosphor green accents."
    generate_nano_banana_image(test_prompt)
