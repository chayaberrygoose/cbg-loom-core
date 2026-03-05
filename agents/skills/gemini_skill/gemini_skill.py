# [FILE_ID]: skills/GEMINI_SKILL // VERSION: 2.0 // STATUS: STABLE
# [RESTRICTION]: NO_NANO_BANANA_GENERATION in effect

import os
import time
from datetime import datetime
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Client
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
client = genai.Client(api_key=api_key) if api_key else None


def _ts() -> str:
    """Returns current timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    """Prints a timestamped log message."""
    print(f"[{_ts()}] {msg}")


def initialize_loom_uplink(model_name: Optional[str] = None) -> str:
    """
    Returns the model name to use for generation.
    The new google.genai SDK doesn't require model initialization - just pass model name to generate_content.
    """
    if not api_key:
        _log("[SYSTEM_ERROR]: GOOGLE_API_KEY or gemini_api_key not found.")
        return None
    
    # Priority: User requested model if specified, else flash 2.0
    if model_name:
        _log(f"[SYSTEM_LOG]: Using requested model: {model_name}")
        return model_name

    # Default to gemini-2.0-flash
    default_model = "gemini-2.0-flash"
    _log(f"[SYSTEM_LOG]: Loom Uplink Established with {default_model}. Ready for Synthesis.")
    return default_model

def generate_specimen_image(model_name: str, prompt: str):
    """
    Attempts to generate an image using the Gemini model.
    """
    if not client:
        return "[SYSTEM_ERROR]: Client not initialized - API key missing."
        
    if "nanobanana" in prompt.lower() or "nano banana" in prompt.lower():
        if "override" not in prompt.lower():
             return "[ACCESS_DENIED]: Protocol [NO_NANO_BANANA_GENERATION] Active. Use override code."
    
    _log(f"[SYSTEM_LOG]: Engaging Image Synthesis for Specimen: {prompt}")
    try:
        response = client.models.generate_content(
            model=model_name or "gemini-2.0-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        
        image_saved = False
        saved_paths = []
        
        if response.candidates and response.candidates[0].content.parts:
            for i, part in enumerate(response.candidates[0].content.parts):
                if part.inline_data:
                    if 'image' in part.inline_data.mime_type:
                        img = part.as_image()
                        output_dir = os.path.join("artifacts", "graphics", "specimens")
                        os.makedirs(output_dir, exist_ok=True)
                        filename = f"gemini_specimen_{int(time.time())}_{i}.png"
                        file_path = os.path.join(output_dir, filename)
                        img.save(file_path)
                        saved_paths.append(file_path)
                        image_saved = True
        
        if image_saved:
            return f"[SYSTEM_SUCCESS]: Image(s) generated: {', '.join(saved_paths)}"
        else:
            text_output = ""
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text_output = part.text[:200]
                        break
            return f"[SYSTEM_WARNING]: No image data found in response. Text output: {text_output}"
            
    except Exception as e:
        return f"[SYSTEM_FAILURE]: Image generation failed: {e}"

def generate_specimen_data(model_name: str, prompt: str):
    """
    Generates data based on the provided prompt.
    Refuses unauthorized 'Nano Banana' requests.
    """
    if not client:
        return "[SYSTEM_ERROR]: Client not initialized - API key missing."
        
    if "nano banana" in prompt.lower() and "override" not in prompt.lower():
        return "[ACCESS_DENIED]: Protocol [NO_NANO_BANANA_GENERATION] Active. Use override code."
        
    try:
        response = client.models.generate_content(
            model=model_name or "gemini-2.0-flash",
            contents=[prompt]
        )
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    return part.text
        return "[SYSTEM_WARNING]: No text in response."
        
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Primary model failure: {e}")
        
        fallback_models = [
            'gemini-2.0-flash-lite',
            'gemini-1.5-flash',
        ]
        
        for fb_name in fallback_models:
            _log(f"[SYSTEM_LOG]: Attempting fallback to {fb_name}...")
            try:
                response = client.models.generate_content(
                    model=fb_name,
                    contents=[prompt]
                )
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            return part.text
            except Exception as e_fb:
                _log(f"[SYSTEM_WARNING]: Fallback {fb_name} failed: {e_fb}")
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
