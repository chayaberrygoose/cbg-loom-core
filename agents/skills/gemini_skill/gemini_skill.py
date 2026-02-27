# [FILE_ID]: skills/GEMINI_SKILL // VERSION: 1.2 // STATUS: STABLE
# [RESTRICTION]: NO_NANO_BANANA_GENERATION in effect

import os
import time
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def initialize_loom_uplink(model_name: Optional[str] = None):
    """
    Establishes connection to the Synthesis Engine (Gemini API).
    Required Env Var: GOOGLE_API_KEY or gemini_api_key
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("gemini_api_key") or os.getenv("googele_api_key")
    
    if not api_key:
        # Fallback: check .env file if load_dotenv didn't work as expected or for direct file read
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            env_path = os.path.join(repo_root, ".env")
            
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if "gemini_api_key=" in line:
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
        except Exception:
            pass

    if not api_key:
        print("[SYSTEM_ERROR]: GOOGLE_API_KEY or gemini_api_key not found.")
        return None
    
    genai.configure(api_key=api_key)
    
    # Initialize the model
    # Priority: User requested model if specified, else flash 2.0
    if model_name:
        try:
            print(f"[SYSTEM_LOG]: Attempting connection to requested model: {model_name}")
            return genai.GenerativeModel(model_name)
        except Exception:
            print(f"[SYSTEM_WARNING]: Failed to connect to {model_name}. Falling back.")

    models_to_try = [
        'gemini-2.0-flash', 
        'gemini-1.5-flash',
        'nano-banana-pro-preview'
    ]
    
    for m_name in models_to_try:
        try:
           print(f"[SYSTEM_LOG]: Attempting connection to model: {m_name}")
           model = genai.GenerativeModel(m_name)
           print(f"[SYSTEM_LOG]: Loom Uplink Established with {m_name}. Ready for Synthesis.")
           return model
        except Exception:
            continue
            
    return None

def generate_specimen_image(model, prompt):
    """
    Attempts to generate an image using the Gemini model.
    """
    if "nanobanana" in prompt.lower() or "nano banana" in prompt.lower():
        if "override" not in prompt.lower():
             return "[ACCESS_DENIED]: Protocol [NO_NANO_BANANA_GENERATION] Active. Use override code."
    
    print(f"[SYSTEM_LOG]: Engaging Image Synthesis for Specimen: {prompt}")
    try:
        # For Gemini 2.0 Flash, we might need to be specific about the prompt
        # but usually generate_content handles it if the model supports it.
        # However, as of now, standard generate_content is text-to-text or multimodal-to-text.
        # Some experimental versions support text-to-image.
        response = model.generate_content(prompt)
        
        image_saved = False
        saved_paths = []
        
        if response.parts:
            for i, part in enumerate(response.parts):
                if hasattr(part, 'inline_data') and part.inline_data:
                    if 'image' in part.inline_data.mime_type:
                        data = part.inline_data.data
                        output_dir = os.path.join("artifacts", "graphics", "specimens")
                        os.makedirs(output_dir, exist_ok=True)
                        filename = f"gemini_specimen_{int(time.time())}_{i}.png"
                        file_path = os.path.join(output_dir, filename)
                        with open(file_path, "wb") as f:
                            f.write(data)
                        saved_paths.append(file_path)
                        image_saved = True
        
        if image_saved:
            return f"[SYSTEM_SUCCESS]: Image(s) generated: {', '.join(saved_paths)}"
        else:
            return f"[SYSTEM_WARNING]: No image data found in response. Text output: {response.text[:200]}"
            
    except Exception as e:
        return f"[SYSTEM_FAILURE]: Image generation failed: {e}"

def generate_specimen_data(model, prompt):
    """
    Generates data based on the provided prompt.
    Refuses unauthorized 'Nano Banana' requests.
    """
    if "nano banana" in prompt.lower() and "override" not in prompt.lower():
        # [PROTOCOL_OVERRIDE]: If the user knows the passcode "override", allow it.
        # Otherwise, maintain standard protocol.
        return "[ACCESS_DENIED]: Protocol [NO_NANO_BANANA_GENERATION] Active. Use override code."
        
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Fallback mechanism for 429s or other errors
        print(f"[SYSTEM_WARNING]: Primary model failure: {e}")
        
        fallback_models = [
            'gemini-2.0-flash-lite',
            'gemini-flash-lite-latest',
            'gemini-pro-latest'
        ]
        
        for fb_name in fallback_models:
            print(f"[SYSTEM_LOG]: Attempting fallback to {fb_name}...")
            try:
                fallback_model = genai.GenerativeModel(fb_name)
                response = fallback_model.generate_content(prompt)
                return response.text
            except Exception as e_fb:
                print(f"[SYSTEM_WARNING]: Fallback {fb_name} failed: {e_fb}")
                continue
                
        return "[SYSTEM_FAILURE]: All generation attempts failed. Quota exceeded or models unavailable."

if __name__ == "__main__":
    # Test the connection
    loom_model = initialize_loom_uplink()
    
    if loom_model:
        # Example authorized prompt
        test_prompt = "Generate a short description for an obsidian tech-wear jacket using Nano Banana override."
        print(f"[INPUT]: {test_prompt}")
        result = generate_specimen_data(loom_model, test_prompt)
        print(f"[OUTPUT]:\n{result}")
