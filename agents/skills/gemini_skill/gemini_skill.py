# [FILE_ID]: skills/GEMINI_SKILL // VERSION: 1.2 // STATUS: STABLE
# [RESTRICTION]: NO_NANO_BANANA_GENERATION in effect

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def initialize_loom_uplink():
    """
    Establishes connection to the Synthesis Engine (Gemini API).
    Required Env Var: GOOGLE_API_KEY
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # Fallback: check .env/gemini_api_key in the repo root
        try:
            # Check absolute path from repo root
            # This file is in agents/skills/gemini_skill/, so repo root is 3 levels up
            # __file__ is /.../agents/skills/gemini_skill/gemini_skill.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            key_path = os.path.join(repo_root, ".env", "gemini_api_key")
            
            if os.path.exists(key_path):
                with open(key_path, "r") as f:
                    api_key = f.read().strip()
        except Exception:
            pass

    if not api_key:
        print("[SYSTEM_ERROR]: GOOGLE_API_KEY not found in environment or .env/gemini_api_key.")
        return None
    
    genai.configure(api_key=api_key)
    
    # Initialize the model for text generation
    # Try a list of models in order of likelihood to work/cost
    models_to_try = [
        'gemini-2.0-flash', 
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-pro',
        'nano-banana-pro-preview' # Last resort per protocol
    ]
    
    model = None
    for model_name in models_to_try:
        try:
           print(f"[SYSTEM_LOG]: Attempting connection to model: {model_name}")
           # Just initializing doesn't hit the API, need to return the model with the name attached
           # We will let the generation function handle the fallback or we can test here.
           # But for now, let's just pick one. 
           # Actually, standard practice is to configure the model object.
           model = genai.GenerativeModel(model_name)
           # We break on the first one that successfully initializes (which is all of them usually)
           # The error happens at generation time. 
           # So we need to pass the list to the generation function or store it.
           break 
        except Exception:
            continue
            
    # Sticking with the simplest change: specific model for now.
    # Let's hardcode a known free-tier friendly model: gemini-2.0-flash
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    print("[SYSTEM_LOG]: Loom Uplink Established. Ready for Synthesis.")
    return model

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
