# [FILE_ID]: scripts/FABRICATE_SPECIMEN_V2 // VERSION: 2.0 // STATUS: STABLE
# [SYSTEM_LOG]: AGILE_NANOBANANA_FABRICATION_PROTOCOL_V2 // REMIX_PROTOCOL_ONLINE

import sys
import os
import argparse
import random
import re
import time
import requests
import io
import json
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image
from agents.skills.fabricator.fabricator import Fabricator

LORE_DIR = Path("artifacts/lore")
PROTOCOL_DIR = Path("protocols")
STAMP_PATH = Path("artifacts/graphics/logos/repo_portal_qr.png")
TEMPLATE_HISTORY_PATH = Path("artifacts/.last_template_id")

def load_theme(theme_name: str) -> dict:
    """
    Loads a theme from artifacts/lore/<theme_name>.md.
    Returns dict with keys: name, description, palette, motifs, prompt_modifiers.
    """
    theme_file = LORE_DIR / f"{theme_name}.md"
    if not theme_file.exists():
        print(f"!! [WARNING]: No lore file for '{theme_name}'. Using name-only fallback.")
        return {"name": theme_name, "prompt_modifiers": ""}

    content = theme_file.read_text(encoding="utf-8")
    theme = {"name": theme_name, "description": "", "palette": "", "motifs": "", "prompt_modifiers": ""}
    current_section = None

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip().lower().replace(" ", "_")
            continue
        if current_section and stripped:
            existing = theme.get(current_section, "")
            theme[current_section] = (existing + " " + stripped).strip() if existing else stripped

    return theme


def list_available_themes() -> list:
    """Lists all theme names from artifacts/lore/*.md files."""
    if not LORE_DIR.exists():
        return []
    return sorted([f.stem for f in LORE_DIR.glob("*.md")])


def load_remix_protocol() -> dict:
    """
    Parses protocols/Remix Protocol.md and extracts high-value combinations.
    Returns dict with keys: combos (list of {base, breach, description}), branding_color.
    """
    protocol_file = PROTOCOL_DIR / "Remix Protocol.md"
    if not protocol_file.exists():
        print("!! [WARNING]: Remix Protocol not found. Falling back to random pairing.")
        return {"combos": [], "branding_color": "#39FF14"}

    content = protocol_file.read_text(encoding="utf-8")
    combos = []

    # Parse high-value combinations: "**Name:** Base: X // Breach: Y. (description)"
    combo_pattern = re.compile(
        r"\*\*(.+?):\*\*\s*Base:\s*(.+?)\s*//\s*Breach:\s*(.+?)\.\s*\((.+?)\)",
        re.IGNORECASE
    )
    for match in combo_pattern.finditer(content):
        combos.append({
            "name": match.group(1).strip(),
            "base": match.group(2).strip(),
            "breach": match.group(3).strip(),
            "description": match.group(4).strip()
        })

    return {"combos": combos, "branding_color": "#39FF14"}


def select_remix_pair(base_override=None, breach_override=None) -> tuple:
    """
    Selects a Base & Breach lore pair for the Remix Protocol.
    Returns (base_name, breach_name, combo_description).
    """
    available = list_available_themes()
    if not available:
        raise ValueError("No lore files found in artifacts/lore/. Cannot execute Remix Protocol.")

    # Explicit overrides take priority
    if base_override and breach_override:
        return (base_override, breach_override, "Manual remix selection")

    # Try to use high-value combos from the protocol
    protocol = load_remix_protocol()
    valid_combos = [
        c for c in protocol["combos"]
        if c["base"] in available and c["breach"] in available
    ]

    if valid_combos:
        combo = random.choice(valid_combos)
        print(f"[SYSTEM_LOG]: Remix Protocol selected combo: {combo['name']}")
        return (combo["base"], combo["breach"], combo["description"])

    # Fallback: random pair (ensuring they're different)
    if len(available) < 2:
        print("!! [WARNING]: Only 1 lore file available. Using same lore for Base & Breach.")
        return (available[0], available[0], "Single-lore fallback")

    pair = random.sample(available, 2)
    print(f"[SYSTEM_LOG]: Random remix pair selected: {pair[0]} x {pair[1]}")
    return (pair[0], pair[1], f"Random fusion of {pair[0]} and {pair[1]}")


def apply_unverified_stamp(image_path: str) -> str:
    """
    Composites the STATUS: UNVERIFIED stamp (repo_portal_qr.png) onto the image.
    The stamp is applied as the final layer per the Remix Protocol branding constraint.
    Returns the path to the stamped image.
    """
    if not STAMP_PATH.exists():
        print(f"!! [WARNING]: Stamp not found at {STAMP_PATH}. Skipping stamp.")
        return image_path

    try:
        base_img = Image.open(image_path).convert("RGBA")
        stamp = Image.open(str(STAMP_PATH)).convert("RGBA")

        # Scale stamp to ~12% of image width
        stamp_size = max(int(base_img.width * 0.12), 48)
        stamp = stamp.resize((stamp_size, stamp_size), Image.LANCZOS)

        # Position: bottom-right corner with padding
        padding = int(base_img.width * 0.03)
        x = base_img.width - stamp_size - padding
        y = base_img.height - stamp_size - padding

        # Composite
        base_img.paste(stamp, (x, y), stamp)
        base_img.save(image_path)
        print(f"// STAMP_APPLIED: STATUS: UNVERIFIED @ ({x}, {y})")
        return image_path
    except Exception as e:
        print(f"!! [WARNING]: Stamp application failed: {e}")
        return image_path


def generate_context_prompt(theme, role, base_prompt=None, theme_data=None, base_data=None, breach_data=None):
    """
    Synthesizes a role-specific Nanobanana prompt.
    In Remix Protocol mode (base_data + breach_data), the Base lore drives structural
    elements (tiles/silhouette) and the Breach lore drives interference (textures/glitch/color).
    Falls back to single-theme mode if only theme_data is provided.
    """
    if base_prompt:
        return f"CBG Studio | {theme} Style: {base_prompt}"
    
    role_modifiers = {
        "tile": "seamless textile pattern, repeatable surface design, flat layout, architectural motif",
        "texture": "macro material detail, industrial surface texture, weathered finish, high-fidelity map",
        "logo": "minimalist vector icon, clinical stamp, high-contrast sigil, white or black background",
        "standalone": "high-fidelity 4k render, industrial noir aesthetic, cinematic lighting, sharp detail"
    }
    
    modifier = role_modifiers.get(role, role_modifiers["standalone"])
    
    # --- REMIX PROTOCOL: Base & Breach Fusion ---
    if base_data and breach_data:
        base_mods = base_data.get("prompt_modifiers", "")
        breach_mods = breach_data.get("prompt_modifiers", "")
        base_name = base_data.get("name", "Unknown")
        breach_name = breach_data.get("name", "Unknown")

        if role == "tile":
            # Tiles = Base (Structure) with Breach interference bleeding in
            lore_injection = f", {base_mods}" if base_mods else ""
            bleed = f", subtle interference: {breach_mods}" if breach_mods else ""
            return (
                f"CBG Studio | REMIX [{base_name} x {breach_name}]: "
                f"{modifier}{lore_injection}{bleed}, "
                f"industrial noir color palette, phosphor green accents, sharp details, high contrast."
            )
        elif role == "texture":
            # Textures = Breach (Interference) with Base structural echoes
            lore_injection = f", {breach_mods}" if breach_mods else ""
            echo = f", structural echo: {base_mods}" if base_mods else ""
            return (
                f"CBG Studio | REMIX [{base_name} x {breach_name}]: "
                f"{modifier}{lore_injection}{echo}, "
                f"industrial noir color palette, phosphor green accents, sharp details, high contrast."
            )
        else:
            # Standalone/mockup: full fusion
            combined = ""
            if base_mods:
                combined += f", base structure: {base_mods}"
            if breach_mods:
                combined += f", breach interference: {breach_mods}"
            return (
                f"CBG Studio | REMIX [{base_name} x {breach_name}]: "
                f"{modifier}{combined}, "
                f"industrial noir color palette, phosphor green accents, sharp details, high contrast."
            )
    
    # --- SINGLE-THEME FALLBACK ---
    lore_modifiers = ""
    if theme_data and theme_data.get("prompt_modifiers"):
        lore_modifiers = f", {theme_data['prompt_modifiers']}"
    
    return f"CBG Studio | {theme} Aesthetics: {modifier}{lore_modifiers}, industrial noir color palette, phosphor green accents, sharp details, high contrast."

def synthesize_lifestyle_mockup(theme, product_title, mockup_url, style_ref_dir="artifacts/Lifestyle Photo Reference"):
    """
    Synthesizes a lifestyle image for the product by using the Printify mockup as a base
    and applying Nanobanana's vision guided by the lifestyle reference photos.
    """
    print(f"[SIGNAL_BROADCAST]: Synthesizing Lifestyle Mockup for {product_title}...")
    
    # 1. Fetch the mockup image data
    image_context = None
    try:
        resp = requests.get(mockup_url)
        resp.raise_for_status()
        image_context = Image.open(io.BytesIO(resp.content))
        print(f"✅ [SYSTEM_LOG]: Mockup context secured for Nanobanana synthesis.")
    except Exception as e:
        print(f"⚠️ [SYSTEM_WARNING]: Failed to fetch mockup image for context: {e}")

    # Identify a style reference
    ref_dir = Path(style_ref_dir)
    refs = list(ref_dir.glob("*.PNG")) + list(ref_dir.glob("*.png"))
    chosen_ref = random.choice(refs) if refs else None
    
    # Prompt logic
    ref_desc = "industrial noir techwear aesthetic, high-contrast shadows, clinical warehouse lighting"
    prompt = (
        f"CBG Studio | Lifestyle Realization: A high-fidelity lifestyle photo. "
        f"The subject is the specific apparel product shown in the provided image. "
        f"CRITICAL: The product in the new photo must be EXACTLY identical to the base image. "
        f"You must replicate the pattern, colors, and placement with 100% precision. "
        f"Context: {theme} style. Visual Reference Style: {ref_desc}. "
        f"The shot should be a medium close-up, focusing on the quality and design of the product specimen."
    )
    
    # Routing to standalone artifacts
    output_path = generate_nano_banana_image(
        prompt, 
        graphic_type_override="mockups",
        image_context=image_context
    )
    return output_path

def fabricate_specimen(theme, template_search=None, prompt_override=None,
                       base_name=None, breach_name=None, remix_desc=None,
                       template_id=None):
    load_dotenv()
    fab = Fabricator()
    
    # Determine mode: Remix Protocol (Base & Breach) vs. Single Theme
    is_remix = base_name is not None and breach_name is not None
    base_data = None
    breach_data = None
    theme_data = None

    if is_remix:
        base_data = load_theme(base_name)
        breach_data = load_theme(breach_name)
        display_theme = f"{base_name} x {breach_name}"
        print(f"[SYSTEM_LOG]: ═══ REMIX PROTOCOL ACTIVE ═══")
        print(f"[SYSTEM_LOG]: Base (Structure): {base_name}")
        if base_data.get("description"):
            print(f"  └─ {base_data['description'][:100]}")
        print(f"[SYSTEM_LOG]: Breach (Interference): {breach_name}")
        if breach_data.get("description"):
            print(f"  └─ {breach_data['description'][:100]}")
        if remix_desc:
            print(f"[SYSTEM_LOG]: Fusion: {remix_desc}")
    else:
        theme_data = load_theme(theme)
        display_theme = theme
        print(f"[SYSTEM_LOG]: Initializing Fabrication Ritual for Theme: {theme}")
        if theme_data.get("description"):
            print(f"[SYSTEM_LOG]: Lore loaded — {theme_data['description'][:120]}...")
    
    # 1. Resolve Template
    templates = fab.get_templates()

    # Load last-used template to avoid repeats
    last_template_id = None
    if TEMPLATE_HISTORY_PATH.exists():
        last_template_id = TEMPLATE_HISTORY_PATH.read_text().strip()

    if template_id:
        # Direct template ID provided (e.g. from per-template iteration)
        template = next((t for t in templates if t['id'] == template_id), None)
        if not template:
            print(f"[SYSTEM_WARNING]: Template ID '{template_id}' not found. Selecting random.")
            template = random.choice(templates)
    elif template_search:
        target_templates = [t for t in templates if template_search.lower() in t['title'].lower()]
        if not target_templates:
            print(f"[SYSTEM_WARNING]: No template matching '{template_search}' found. Selecting random.")
            target_templates = templates
        # Exclude last-used from candidates when possible
        filtered = [t for t in target_templates if t['id'] != last_template_id]
        template = random.choice(filtered if filtered else target_templates)
    else:
        # Exclude last-used from random pool when possible
        filtered = [t for t in templates if t['id'] != last_template_id]
        template = random.choice(filtered if filtered else templates)

    # Persist this selection to prevent immediate repeats
    try:
        TEMPLATE_HISTORY_PATH.write_text(template['id'])
    except Exception:
        pass  # Non-critical

    print(f"[SYSTEM_LOG]: Selected Template: {template['title']} (ID: {template['id']})")
    
    # 2. Analyze Roles for the Template
    source = fab.get_product(template['id'])
    
    roles_to_generate = ["tiles", "textures"]
    artifact_paths = {}

    for role in roles_to_generate:
        prompt = generate_context_prompt(
            display_theme, role[:-1],
            base_prompt=prompt_override,
            theme_data=theme_data,
            base_data=base_data,
            breach_data=breach_data
        )
        print(f"[SIGNAL_BROADCAST]: Requesting '{role}' synthesis for '{display_theme}'...")
        
        # This will use the updated nanobanana_skill routing to artifacts/graphics/<role>/...
        result_path = generate_nano_banana_image(prompt, graphic_type_override=role)
        
        if result_path:
            artifact_paths[role] = result_path
            print(f"✅ [SYSTEM_LOG]: Artifact secured: {result_path}")
        else:
            print(f"❌ [SYSTEM_ERROR]: Failed to synthesize {role}")

    if not artifact_paths:
        print("[SYSTEM_ERROR]: No artifacts stabilized. Aborting ritual.")
        return

    # Identifiers for the fabricator
    role_overrides = {}
    
    # We'll pass the local paths to the fabricator via role_overrides.
    print("[SYSTEM_LOG]: Preparing artifact mapping for the Fabricator...")
    for role, path in artifact_paths.items():
        role_type = "tile" if role == "tiles" else "texture"
        role_overrides[role_type] = path

    # 3. Realize Product
    print("[SYSTEM_LOG]: Realizing specimen...")
    
    try:
        # Use fabricate_from_template which handles the cloning and role mapping
        product = fab.fabricate_from_template(
            template['id'], 
            role_overrides=role_overrides
        )
        product_id = product.get('id')
        product_title = product.get('title')
        print(f"\n--- [FABRICATION_COMPLETE]: ID_{product_id} ---")
        print(f"SPECIMEN: {product_title}")
        
        # 4. Lifestyle Realization Step
        print("[SYSTEM_LOG]: Protocol Initiation: LIFESTYLE_REALIZATION")
        
        # We need to RE-FETCH the product to get the mockups generated by Printify after cloning
        time.sleep(5)  # Brief pause for Printify to initialize the specimen
        product = fab.get_product(product_id)
        images = product.get('images', [])
        
        if images:
            # Look for 'front' mockup specifically if possible, else default to first
            mockup_url = images[0].get('src')
            for img in images:
                if 'front' in img.get('variant_ids', []) or 'front' in img.get('src', '').lower():
                    mockup_url = img.get('src')
                    break
                    
            lifestyle_path = synthesize_lifestyle_mockup(display_theme, product_title, mockup_url)
            
            if lifestyle_path:
                # [REMIX_PROTOCOL]: Apply STATUS: UNVERIFIED stamp as final layer
                apply_unverified_stamp(lifestyle_path)
                print(f"[SYSTEM_LOG]: Lifestyle artifact stabilized. Injecting into Conduit...")
                # Ensure the file exists before upload
                if os.path.exists(lifestyle_path):
                    # [SIGNAL_RECOVERY]: Re-check file integrity and ensure binary read if needed
                    file_size = os.path.getsize(lifestyle_path)
                    print(f"// UPLOADING_LIFESTYLE: {lifestyle_path} ({file_size} bytes)")
                    
                    # Printify upload ritual
                    lifestyle_media_id = fab.upload_image(local_path=lifestyle_path, file_name=f"lifestyle_{product_id}.png")
                    # Capture the src URL immediately — upload_image sets last_upload_src
                    lifestyle_src_url = fab.last_upload_src
                    
                    if lifestyle_media_id:
                        print(f"// ARTIFACT_SECURED: ID_{lifestyle_media_id}")
                        print(f"// LIFESTYLE_CDN: {lifestyle_src_url}")
                        
                        # [SYSTEM_NOTE]: Printify product gallery only accepts auto-generated mockups.
                        # Lifestyle image is archived locally with CDN URL for use in external channels.
                        print(f"✅ [SYSTEM_SUCCESS]: Lifestyle mockup realized for {product_id}.")
                        
                        # [LINKAGE_STAMP]: Archive the relationship between Printify Product and Lifestyle Specimen
                        mapping_file = Path(lifestyle_path).parent / "product_link.json"
                        link_data = {
                            "product_id": product_id,
                            "product_title": product_title,
                            "conduit_url": f"https://printify.com/app/store/{fab.shop_id}/products/{product_id}",
                            "lifestyle_media_id": lifestyle_media_id,
                            "lifestyle_src_url": lifestyle_src_url,
                            "lifestyle_local_path": lifestyle_path,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        }
                        mapping_file.write_text(json.dumps(link_data, indent=4))
                        print(f"✅ [SYSTEM_LOG]: Linkage secured: {mapping_file}")
                        
                        # [PROTOCOL_UPDATE]: Rename mockup folder to include product ID
                        old_folder = Path(lifestyle_path).parent
                        new_folder_name = f"{old_folder.name}__{product_id}"
                        new_folder = old_folder.parent / new_folder_name
                        try:
                            old_folder.rename(new_folder)
                            print(f"// FOLDER_RENAMED: {new_folder_name}")
                        except Exception as rename_err:
                            print(f"!! [WARNING]: Folder rename failed: {rename_err}")
                        
                        # [PROTOCOL_UPDATE]: Post blog entry to STATUS: UNVERIFIED
                        fab.post_blog_for_product(
                            product_id=product_id,
                            title=product_title,
                            description=product.get('description', ''),
                            mockups_dir=str(new_folder.parent) if new_folder.exists() else "artifacts/graphics/mockups"
                        )
                    else:
                        print(f"❌ [SYSTEM_ERROR]: Media upload failed to return ID.")
                else:
                    print(f"❌ [SYSTEM_ERROR]: Lifestyle path {lifestyle_path} not found.")
        
        print(f"CONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product_id}")
        return product
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Realization failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBG Agile Specimen Fabrication Protocol // REMIX PROTOCOL")
    
    # Mode selection
    mode_group = parser.add_argument_group("Mode")
    mode_group.add_argument("--theme", type=str, help="Single-theme mode: use one lore file (legacy)")
    mode_group.add_argument("--remix", action="store_true", default=True,
                            help="Remix Protocol mode: fuse Base & Breach lore (default)")
    mode_group.add_argument("--base", type=str, help="Remix: explicit Base (Structure) lore")
    mode_group.add_argument("--breach", type=str, help="Remix: explicit Breach (Interference) lore")
    
    # Fabrication options
    parser.add_argument("--template", type=str, help="Search string for target template (limits to matching templates)")
    parser.add_argument("--prompt", type=str, help="Optional manual prompt override")
    
    # Info
    parser.add_argument("--list-themes", action="store_true", help="List available lore themes and exit")
    parser.add_argument("--list-combos", action="store_true", help="List high-value remix combos and exit")
    
    args = parser.parse_args()
    
    if args.list_themes:
        themes = list_available_themes()
        if themes:
            print(f"[SYSTEM_ECHO]: {len(themes)} lore file(s) available:")
            for t in themes:
                print(f"  - {t}")
        else:
            print("[SYSTEM_WARNING]: No lore files found in artifacts/lore/")
        sys.exit(0)
    
    if args.list_combos:
        protocol = load_remix_protocol()
        if protocol["combos"]:
            print(f"[SYSTEM_ECHO]: {len(protocol['combos'])} high-value combo(s):")
            for c in protocol["combos"]:
                print(f"  [{c['name']}] Base: {c['base']} // Breach: {c['breach']}")
                print(f"    └─ {c['description']}")
        else:
            print("[SYSTEM_WARNING]: No combos parsed from Remix Protocol.")
        sys.exit(0)
    
    # --- Single-theme mode (legacy) ---
    if args.theme:
        print(f"[SYSTEM_LOG]: Single-theme mode: {args.theme}")
        fabricate_specimen(
            args.theme,
            template_search=args.template,
            prompt_override=args.prompt,
        )
        sys.exit(0)
    
    # --- Remix Protocol mode (default) ---
    available = list_available_themes()
    if not available:
        print("[SYSTEM_ERROR]: No lore files available. Add .md files to artifacts/lore/.")
        sys.exit(1)
    
    base_name, breach_name, remix_desc = select_remix_pair(
        base_override=args.base, breach_override=args.breach
    )
    display_theme = f"{base_name} x {breach_name}"
    
    fabricate_specimen(
        theme=display_theme,
        template_search=args.template,
        prompt_override=args.prompt,
        base_name=base_name,
        breach_name=breach_name,
        remix_desc=remix_desc,
    )
