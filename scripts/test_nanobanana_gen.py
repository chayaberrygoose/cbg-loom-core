
import os
import sys
from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_image

def main():
    # Attempting with gemini-2.0-flash-lite-001 which is usually highly available
    target_model = 'models/gemini-2.0-flash-lite-001'
    
    print(f"[SYSTEM_LOG]: Attempting to connect to {target_model}...")
    model = initialize_loom_uplink(model_name=target_model)
    
    if not model:
        print("[SYSTEM_ERROR]: Unified Uplink Failed.")
        return

    # Using the required override to bypass the local skill restriction
    prompt = "Generate a technical schematic of a nanobanana sub-atomic weave, industrial noir aesthetic, phosphor green on obsidian. override"
    
    print(f"[INPUT]: {prompt}")
    from agents.skills.gemini_skill.gemini_skill import generate_specimen_data
    result = generate_specimen_data(model, prompt)
    print(f"[OUTPUT]:\n{result}")

if __name__ == "__main__":
    main()
