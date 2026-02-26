# [FILE_ID]: scripts/generate_image.py // VERSION: 1.0 // STATUS: BETA
import sys
import os
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# Add the repository root to sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(repo_root)

# Load environment variables
load_dotenv(os.path.join(repo_root, ".env/gemini_api_key")) # It seems the key is in .env/gemini_api_key file content, not .env file KEY=VALUE

def get_api_key():
    # Try env var first
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key: return api_key
    
    # Try the file
    key_path = os.path.join(repo_root, ".env", "gemini_api_key")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    return None

def main():
    api_key = get_api_key()
    if not api_key:
        print("[SYSTEM_ERROR]: API Key not found.")
        return

    genai.configure(api_key=api_key)

    # Prompt from arguments or default
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        # Default prompt based on the previous context
        prompt = "Technical apparel textile engineering for Anatomical Lab Shorts, deep obsidian TILING overlayed with fine-line blueprint schematic diagrams. Industrial Noir style."

    print(f"[SYSTEM_LOG]: Engaging Image Synthesis with Prompt: {prompt}")

    # Models that might support image generation
    # Based on previous list: models/gemini-2.0-flash-exp-image-generation
    # models/gemini-3.1-flash-image-preview
    # models/gemini-2.5-flash-image
    
    model_name = 'gemini-2.0-flash-exp' # attempting standard model which might be multimodal
    # Actually, let's try to find an image generation model from the list or use the known one
    # Note: google-generativeai python client usually uses 'imagen-3.0-generate-001' or similar for pure image gen if available,
    # or Gemini models for text-to-image if supported. 
    # Let's try 'gemini-2.0-flash' and see if it returns an image part.
    
    # List of potential image generation models to try
    # Adding specific requests from user: nano banana 2 (flash) -> likely gemini-2.0-flash variants
    candidate_models = [
        'gemini-2.0-flash', # Trying base flash model
        'gemini-2.0-flash-001',
        'gemini-2.0-flash-lite',
        'gemini-flash-latest',
        # Retrying known image models just in case
        'gemini-2.0-flash-exp-image-generation', 
    ]

    for target_model in candidate_models:
        print(f"[SYSTEM_LOG]: Attempting generation with {target_model}...")
        try:
            # Handle Imagen vs Gemini differently
            if "imagen" in target_model.lower():
                try:
                    # Some versions support ImageGenerationModel
                    model = genai.ImageGenerationModel(target_model)
                    response = model.generate_images(prompt=prompt)
                    
                    if response.images:
                        print(f"[SYSTEM_SUCCESS]: Imagen Generation success for {target_model}!")
                        for i, img in enumerate(response.images):
                            filename = f"generated_specimen_{target_model.replace('/','-')}_{i}.png"
                            img.save(filename)
                            print(f"[SYSTEM_SUCCESS]: Image saved to {filename}")
                        return
                    else:
                        print(f"[SYSTEM_WARNING]: {target_model} returned no images.")
                except AttributeError:
                    print(f"[SYSTEM_FAILURE]: ImageGenerationModel class not found in current library version.")
                    continue
            else:
                # Regular Gemini models
                model = genai.GenerativeModel(target_model)
                response = model.generate_content(prompt)
                
                if not response.parts:
                    print(f"[SYSTEM_WARNING]: {target_model} returned no parts.")
                    continue

                print(f"[SYSTEM_LOG]: Generation success with {target_model}. Analyzing Output...")
                
                image_saved = False
                for i, part in enumerate(response.parts):
                     # Try to identify image data
                     if hasattr(part, 'inline_data') and part.inline_data:
                         # print(f"[SYSTEM_SUCCESS]: Found inline data (MIME: {part.inline_data.mime_type})") # Debug
                         if 'image' in part.inline_data.mime_type:
                             import base64
                             # Part.inline_data.data is usually bytes in the python client if using google-generativeai
                             # But sometimes it's b64 string. 
                             # Let's assume bytes first.
                             data = part.inline_data.data
                             
                             filename = f"generated_specimen_{target_model.replace('/','-')}_{i}.png"
                             with open(filename, "wb") as f:
                                f.write(data)
                             print(f"[SYSTEM_SUCCESS]: Image saved to {filename}")
                             image_saved = True
                     elif hasattr(part, 'text') and part.text:
                         # Check if text is just an error or refusal
                         if "draw" in part.text.lower() or "cannot" in part.text.lower():
                             print(f"[TEXT REFUSAL]: {part.text[:100]}...")
                             pass
                         else:
                            print(f"[TEXT OUTPUT]: {part.text[:100]}...")
                
                if image_saved:
                    return # Stop if we got an image

        except Exception as e:
            if "429" in str(e):
                print(f"[SYSTEM_WARNING]: Quota exceeded for {target_model}.")
            elif "404" in str(e):
                print(f"[SYSTEM_WARNING]: Model {target_model} not found.")
            else:
                 print(f"[SYSTEM_FAILURE]: {target_model} error: {e}")

if __name__ == "__main__":
    main()
