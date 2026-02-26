# [FILE_ID]: scripts/generate_mj_prompt.py // VERSION: 1.0 // STATUS: BETA
import sys
import os

# Add the repository root to sys.path to allow importing from agents.skills
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(repo_root)

from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data

def load_protocol():
    protocol_path = os.path.join(repo_root, "protocols", "swatch_engineering_v2")
    with open(protocol_path, "r") as f:
        return f.read()

def load_product(file_path):
    with open(file_path, "r") as f:
        return f.read()

def main():
    # Target file (defaulting to the one in context)
    target_file = os.path.join(repo_root, "artifacts/catalog/69925cac064523edc10c61f6/C_B_G__Studio___Anatomical_Lab_Shorts___Sacred___P.md")
    
    if len(sys.argv) > 1:
        target_file = sys.argv[1]

    print(f"[SYSTEM_LOG]: Loading Specimen Data: {target_file}")
    
    try:
        product_content = load_product(target_file)
        protocol_content = load_protocol()
    except FileNotFoundError as e:
        print(f"[SYSTEM_ERROR]: File Access Failed - {e}")
        return

    # Construct the Loom Directive
    loom_prompt = f"""
    [ROLE]: You are the Loom, a digital architect for "Chaya Berry Goose" (Industrial Noir/Tech-Wear).
    
    [TASK]: Generate a high-fidelity Midjourney Prompt for the following product, adhering to the provided SWATCH_ENGINEERING_V2 protocol.
    
    [PROTOCOL_DATA]:
    {protocol_content}
    
    [SPECIMEN_DATA]:
    {product_content}
    
    [OUTPUT_FORMAT]:
    Provide ONLY the Midjourney prompt string, starting with "/imagine prompt:".
    Ensure the prompt includes technical parameters (e.g., --tile, --v 6.0, --style raw) as specified in the protocol.
    Use the [Lab Vocabulary] and [Design Primitives] relevant to the product description.
    """

    # Engage Synthesis
    print("[SYSTEM_LOG]: Engaging Synthesis Engine...")
    model = initialize_loom_uplink()
    
    if model:
        result = generate_specimen_data(model, loom_prompt)
        print("\n--- [SYNTHESIS COMPLETE] ---\n")
        print(result)
        print("\n----------------------------\n")

if __name__ == "__main__":
    main()
