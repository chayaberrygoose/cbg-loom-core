# [FILE_ID]: scripts/generate_image.py // VERSION: 2.0 // STATUS: STABLE
import sys
import os
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Add the repository root to sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(repo_root)

# Load environment variables
load_dotenv()


def _ts() -> str:
    """Returns current timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    """Prints a timestamped log message."""
    print(f"[{_ts()}] {msg}")


def get_api_key():
    # Try env var first
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
    if api_key:
        return api_key
    return None


def main():
    api_key = get_api_key()
    if not api_key:
        _log("[SYSTEM_ERROR]: API Key not found.")
        return

    client = genai.Client(api_key=api_key)

    # Prompt from arguments or default
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        # Default prompt based on the previous context
        prompt = "Technical apparel textile engineering for Anatomical Lab Shorts, deep obsidian TILING overlayed with fine-line blueprint schematic diagrams. Industrial Noir style."

    _log(f"[SYSTEM_LOG]: Engaging Image Synthesis with Prompt: {prompt}")

    # Models that support image generation
    candidate_models = [
        'gemini-3.1-flash-image-preview',
        'gemini-2.0-flash',
    ]

    for target_model in candidate_models:
        _log(f"[SYSTEM_LOG]: Attempting generation with {target_model}...")
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1"
                    )
                )
            )

            if not response.candidates or not response.candidates[0].content.parts:
                _log(f"[SYSTEM_WARNING]: {target_model} returned no parts.")
                continue

            _log(f"[SYSTEM_LOG]: Generation success with {target_model}. Analyzing Output...")
            
            image_saved = False
            for i, part in enumerate(response.candidates[0].content.parts):
                if part.inline_data:
                    if 'image' in part.inline_data.mime_type:
                        img = part.as_image()
                        filename = f"generated_specimen_{target_model.replace('/', '-')}_{i}.png"
                        img.save(filename)
                        _log(f"[SYSTEM_SUCCESS]: Image saved to {filename}")
                        image_saved = True
                elif part.text:
                    if "cannot" in part.text.lower() or "draw" in part.text.lower():
                        _log(f"[TEXT REFUSAL]: {part.text[:100]}...")
                    else:
                        _log(f"[TEXT OUTPUT]: {part.text[:100]}...")
            
            if image_saved:
                return  # Stop if we got an image

        except Exception as e:
            if "429" in str(e):
                _log(f"[SYSTEM_WARNING]: Quota exceeded for {target_model}.")
            elif "404" in str(e):
                _log(f"[SYSTEM_WARNING]: Model {target_model} not found.")
            else:
                _log(f"[SYSTEM_FAILURE]: {target_model} error: {e}")

    _log("[SYSTEM_FAILURE]: All models failed to generate an image.")


if __name__ == "__main__":
    main()
