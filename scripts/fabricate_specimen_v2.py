# [FILE_ID]: scripts/FABRICATE_SPECIMEN_V2 // VERSION: 2.3 // STATUS: STABLE
# [SYSTEM_LOG]: AGILE_NANOBANANA_FABRICATION_PROTOCOL_V2 // REMIX_PROTOCOL_ONLINE
# [SYSTEM_LOG]: EQUAL_WEIGHT_LORE_SELECTION — USAGE_TRACKER_ENABLED
# [SYSTEM_LOG]: SHOPIFY_PUBLISH_INTEGRATED — BLOG_STEP_REMOVED

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
from scripts.publish_printify_product import (
    set_margin_and_publish,
    wait_for_printify_publish,
    upload_lifestyle_image,
    get_printify_shop_id,
)

LORE_DIR = Path("artifacts/lore")
PROTOCOL_DIR = Path("protocols")
STAMP_PATH = Path("artifacts/graphics/logos/repo_portal_qr.png")
TEMPLATE_HISTORY_PATH = Path("artifacts/.last_template_id")
RECOMMENDATIONS_PATH = Path("artifacts/recommendations/pipeline_recommendations.json")
LORE_USAGE_PATH = Path("artifacts/.lore_usage.json")


def _ts() -> str:
    """Returns current timestamp for logging."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    """Prints a timestamped log message."""
    print(f"[{_ts()}] {msg}")


# Palette of accent colors used when no explicit color is provided.
# A random entry is chosen once per process to avoid bias toward any single hue.
_ACCENT_PALETTE = [
    ("phosphor green", "#39FF14"),
    ("infrared red", "#FF2400"),
    ("electric cyan", "#00FFFF"),
    ("deep amber", "#FFBF00"),
    ("ultraviolet purple", "#7F00FF"),
    ("signal white", "#F5F5F5"),
    ("cobalt blue", "#0047AB"),
    ("plasma magenta", "#FF0090"),
    ("molten orange", "#FF6600"),
    ("static silver", "#C0C0C0"),
]

# Select once per process so every prompt in a single run shares the same accent.
_SELECTED_ACCENT = random.choice(_ACCENT_PALETTE)


def _random_accent() -> str:
    """Return the accent color descriptor selected for this run."""
    return _SELECTED_ACCENT[0]


def _random_accent_hex() -> str:
    """Return the accent hex color selected for this run."""
    return _SELECTED_ACCENT[1]


def load_recommendations() -> dict:
    """
    Load pipeline recommendations from feedback analysis.
    Returns empty config if file doesn't exist.
    """
    if not RECOMMENDATIONS_PATH.exists():
        return {}
    
    try:
        with open(RECOMMENDATIONS_PATH, "r", encoding="utf-8") as f:
            recs = json.load(f)
        print("[SYSTEM_LOG]: Pipeline recommendations loaded.")
        return recs
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Failed to load recommendations: {e}")
        return {}


def filter_templates_by_recommendations(templates: list, recs: dict) -> list:
    """
    Apply recommendation-based filtering to template list.
    Deprioritizes avoided templates, prioritizes preferred ones.
    Returns reordered/filtered list.
    """
    config = recs.get("pipeline_config_suggestions", {})
    avoid_terms = [t.lower() for t in config.get("avoid_garments", [])]
    prefer_terms = [t.lower() for t in config.get("prefer_garments", [])]
    
    if not avoid_terms and not prefer_terms:
        return templates
    
    def score_template(t):
        title_lower = t.get("title", "").lower()
        score = 0
        # Boost for preferred templates
        for term in prefer_terms:
            if term in title_lower:
                score += 10
        # Penalty for avoided templates (but don't exclude entirely)
        for term in avoid_terms:
            if term in title_lower:
                score -= 5
        return score
    
    # Sort by score descending, then shuffle within same score for variety
    scored = [(t, score_template(t)) for t in templates]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Group by score and shuffle within groups
    from itertools import groupby
    result = []
    for _, group in groupby(scored, key=lambda x: x[1]):
        group_list = [t for t, _ in group]
        random.shuffle(group_list)
        result.extend(group_list)
    
    if prefer_terms or avoid_terms:
        top_template = result[0] if result else None
        if top_template:
            print(f"[SYSTEM_LOG]: Template prioritization active. Top candidates favor: {', '.join(prefer_terms) or 'any'}")
    
    return result


def get_recommendation_prompt_modifiers(recs: dict) -> tuple:
    """
    Extract prompt modifiers from recommendations.
    Returns (modifiers_to_add: list, modifiers_to_avoid: list)
    """
    config = recs.get("pipeline_config_suggestions", {})
    add_mods = config.get("prompt_modifiers_add", [])
    avoid_mods = config.get("prompt_modifiers_avoid", [])
    return (add_mods, avoid_mods)

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


# ─── LORE USAGE TRACKER ────────────────────────────────────────────

def _load_usage() -> dict:
    """Load lore usage counts from disk. Returns {theme_name: int}."""
    if LORE_USAGE_PATH.exists():
        try:
            return json.loads(LORE_USAGE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_usage(usage: dict) -> None:
    """Persist usage counts to disk."""
    try:
        LORE_USAGE_PATH.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Failed to save lore usage tracker: {e}")


def record_lore_usage(*theme_names: str) -> None:
    """Increment the usage counter for one or more lore themes."""
    usage = _load_usage()
    for name in theme_names:
        usage[name] = usage.get(name, 0) + 1
    _save_usage(usage)


def select_least_used(available: list, count: int = 1, exclude: list = None) -> list:
    """
    Select `count` themes from `available` that have the lowest usage.
    Ties are broken randomly for natural variety.

    Args:
        available: List of theme names to choose from.
        count:     How many to select (1 for single, 2 for remix pair).
        exclude:   Theme names to skip (e.g. already-chosen base).

    Returns:
        List of selected theme names.
    """
    usage = _load_usage()
    exclude = set(exclude or [])
    pool = [t for t in available if t not in exclude]

    if not pool:
        pool = list(available)  # fallback: ignore exclusions

    if len(pool) <= count:
        return pool[:count]

    # Sort by usage (ascending), shuffle ties
    random.shuffle(pool)  # pre-shuffle so equal-usage themes are randomized
    pool.sort(key=lambda t: usage.get(t, 0))

    return pool[:count]


def load_remix_protocol() -> dict:
    """
    Parses protocols/Remix Protocol.md and extracts high-value combinations.
    Returns dict with keys: combos (list of {base, breach, description}), branding_color.
    """
    protocol_file = PROTOCOL_DIR / "Remix Protocol.md"
    if not protocol_file.exists():
        print("!! [WARNING]: Remix Protocol not found. Falling back to random pairing.")
        return {"combos": [], "branding_color": _random_accent_hex()}

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

    return {"combos": combos, "branding_color": _random_accent_hex()}


def select_remix_pair(base_override=None, breach_override=None) -> tuple:
    """
    Selects a Base & Breach lore pair for the Remix Protocol.
    Uses usage-weighted selection so all lore files get roughly equal rotation.
    Named combos from the Remix Protocol are still eligible but no longer prioritized.
    Returns (base_name, breach_name, combo_description).
    """
    available = list_available_themes()
    if not available:
        raise ValueError("No lore files found in artifacts/lore/. Cannot execute Remix Protocol.")

    # Explicit overrides take priority
    if base_override and breach_override:
        return (base_override, breach_override, "Manual remix selection")

    if len(available) < 2:
        print("!! [WARNING]: Only 1 lore file available. Using same lore for Base & Breach.")
        return (available[0], available[0], "Single-lore fallback")

    # Select base from least-used themes
    base_picks = select_least_used(available, count=1)
    base_name = base_picks[0]

    # Select breach from least-used themes, excluding the base
    breach_picks = select_least_used(available, count=1, exclude=[base_name])
    breach_name = breach_picks[0]

    # Check if this pair happens to match a named combo (for logging only)
    protocol = load_remix_protocol()
    combo_match = next(
        (c for c in protocol["combos"]
         if (c["base"] == base_name and c["breach"] == breach_name)
         or (c["base"] == breach_name and c["breach"] == base_name)),
        None
    )

    if combo_match:
        desc = f"{combo_match['name']}: {combo_match['description']}"
        print(f"[SYSTEM_LOG]: Usage-weighted selection landed on known combo: {combo_match['name']}")
    else:
        desc = f"Balanced fusion of {base_name} and {breach_name}"
        print(f"[SYSTEM_LOG]: Usage-weighted remix pair: {base_name} x {breach_name}")

    return (base_name, breach_name, desc)


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
                f"industrial noir color palette, {_random_accent()} accents, sharp details, high contrast."
            )
        elif role == "texture":
            # Textures = Breach (Interference) with Base structural echoes
            lore_injection = f", {breach_mods}" if breach_mods else ""
            echo = f", structural echo: {base_mods}" if base_mods else ""
            return (
                f"CBG Studio | REMIX [{base_name} x {breach_name}]: "
                f"{modifier}{lore_injection}{echo}, "
                f"industrial noir color palette, {_random_accent()} accents, sharp details, high contrast."
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
                f"industrial noir color palette, {_random_accent()} accents, sharp details, high contrast."
            )
    
    # --- SINGLE-THEME FALLBACK ---
    lore_modifiers = ""
    if theme_data and theme_data.get("prompt_modifiers"):
        lore_modifiers = f", {theme_data['prompt_modifiers']}"
    
    return f"CBG Studio | {theme} Aesthetics: {modifier}{lore_modifiers}, industrial noir color palette, {_random_accent()} accents, sharp details, high contrast."

def synthesize_lifestyle_mockup(theme, product_title, mockup_url, style_ref_dir="artifacts/Lifestyle Photo Reference", blueprint_meta=None):
    """
    Synthesizes a lifestyle image for the product by using the Printify mockup as a base
    and applying Nanobanana's vision guided by the lifestyle reference photos.
    
    Args:
        blueprint_meta: Optional dict from parse_blueprint_metadata() with gender/garment/model info.
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
    
    # [METADATA_THREAD]: Build gender/garment-aware subject description
    meta = blueprint_meta or {}
    model_desc = meta.get('model', 'a model')
    garment_desc = meta.get('garment', 'apparel product')
    subject_line = f"The subject is {model_desc} wearing the {garment_desc.lower()} shown in the provided image."
    
    # Prompt logic
    ref_desc = "industrial noir techwear aesthetic, high-contrast shadows, clinical warehouse lighting"
    prompt = (
        f"CBG Studio | Lifestyle Realization: A high-fidelity lifestyle photo. "
        f"{subject_line} "
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
                       template_id=None, tile_scale=None):
    load_dotenv()
    fab = Fabricator()
    
    # Load static recommendations if they exist (no longer auto-refreshed from blog)
    recommendations = load_recommendations()
    rec_add_mods, rec_avoid_mods = get_recommendation_prompt_modifiers(recommendations)
    
    # Determine mode: Remix Protocol (Base & Breach) vs. Single Theme
    is_remix = base_name is not None and breach_name is not None
    base_data = None
    breach_data = None
    theme_data = None

    if is_remix:
        base_data = load_theme(base_name)
        breach_data = load_theme(breach_name)
        display_theme = f"{base_name} x {breach_name}"
        _log(f"[SYSTEM_LOG]: ═══ REMIX PROTOCOL ACTIVE ═══")
        _log(f"[SYSTEM_LOG]: Base (Structure): {base_name}")
        if base_data.get("description"):
            print(f"  └─ {base_data['description'][:100]}")
        _log(f"[SYSTEM_LOG]: Breach (Interference): {breach_name}")
        if breach_data.get("description"):
            print(f"  └─ {breach_data['description'][:100]}")
        if remix_desc:
            _log(f"[SYSTEM_LOG]: Fusion: {remix_desc}")
    else:
        theme_data = load_theme(theme)
        display_theme = theme
        _log(f"[SYSTEM_LOG]: Initializing Fabrication Ritual for Theme: {theme}")
        if theme_data.get("description"):
            _log(f"[SYSTEM_LOG]: Lore loaded — {theme_data['description'][:120]}...")
    
    # Record lore usage for equal-weight tracking
    if is_remix:
        record_lore_usage(base_name, breach_name)
        _log(f"[SYSTEM_LOG]: Usage recorded for {base_name}, {breach_name}")
    else:
        record_lore_usage(theme)
        _log(f"[SYSTEM_LOG]: Usage recorded for {theme}")
    
    # 1. Resolve Template (with recommendation-based filtering)
    templates = fab.get_templates()
    templates = filter_templates_by_recommendations(templates, recommendations)

    # Load last-used template to avoid repeats
    last_template_id = None
    if TEMPLATE_HISTORY_PATH.exists():
        last_template_id = TEMPLATE_HISTORY_PATH.read_text().strip()

    if template_id:
        # Direct template ID provided (e.g. from per-template iteration)
        template = next((t for t in templates if t['id'] == template_id), None)
        if not template:
            _log(f"[SYSTEM_WARNING]: Template ID '{template_id}' not found. Selecting random.")
            template = random.choice(templates)
    elif template_search:
        target_templates = [t for t in templates if template_search.lower() in t['title'].lower()]
        if not target_templates:
            _log(f"[SYSTEM_WARNING]: No template matching '{template_search}' found. Selecting random.")
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

    _log(f"[SYSTEM_LOG]: Selected Template: {template['title']} (ID: {template['id']})")
    
    # 2. Analyze Roles for the Template — only generate images that will actually be used
    required_roles = fab.analyze_template_roles(template['id'])
    
    # Map role names to folder names: tile -> tiles, texture -> textures
    role_to_folder = {'tile': 'tiles', 'texture': 'textures', 'logo': 'logos'}
    roles_to_generate = [role_to_folder[r] for r in required_roles if r in role_to_folder and r != 'logo']
    
    if not roles_to_generate:
        _log("[SYSTEM_WARNING]: Template has no tile/texture roles. Defaulting to tiles.")
        roles_to_generate = ["tiles"]
    
    _log(f"[SYSTEM_LOG]: Generating {len(roles_to_generate)} image(s): {roles_to_generate}")
    
    artifact_paths = {}

    for role in roles_to_generate:
        prompt = generate_context_prompt(
            display_theme, role[:-1],
            base_prompt=prompt_override,
            theme_data=theme_data,
            base_data=base_data,
            breach_data=breach_data
        )
        
        # Apply recommendation-based prompt modifiers
        if rec_add_mods:
            prompt += ", " + ", ".join(rec_add_mods)
        if rec_avoid_mods:
            # Add as negative guidance
            prompt += f", avoid: {', '.join(rec_avoid_mods)}"
        
        _log(f"[SIGNAL_BROADCAST]: Requesting '{role}' synthesis for '{display_theme}'...")
        
        # This will use the updated nanobanana_skill routing to artifacts/graphics/<role>/...
        result_path = generate_nano_banana_image(prompt, graphic_type_override=role)
        
        if result_path:
            artifact_paths[role] = result_path
            _log(f"✅ [SYSTEM_LOG]: Artifact secured: {result_path}")
        else:
            _log(f"❌ [SYSTEM_ERROR]: Failed to synthesize {role}")

    if not artifact_paths:
        _log("[SYSTEM_ERROR]: No artifacts stabilized. Aborting ritual.")
        return

    # Identifiers for the fabricator
    role_overrides = {}
    
    # We'll pass the local paths to the fabricator via role_overrides.
    _log("[SYSTEM_LOG]: Preparing artifact mapping for the Fabricator...")
    for role, path in artifact_paths.items():
        role_type = "tile" if role == "tiles" else "texture"
        role_overrides[role_type] = path

    # 3. Realize Product
    _log("[SYSTEM_LOG]: Realizing specimen...")
    
    try:
        # Use fabricate_from_template which handles the cloning and role mapping
        product = fab.fabricate_from_template(
            template['id'], 
            role_overrides=role_overrides,
            tile_scale=tile_scale,
        )
        product_id = product.get('id')
        product_title = product.get('title')
        blueprint_meta = product.get('_blueprint_meta', {})
        _log(f"--- [FABRICATION_COMPLETE]: ID_{product_id} ---")
        _log(f"SPECIMEN: {product_title}")
        
        # 4. Set Margin + Publish to Shopify
        _log("[SYSTEM_LOG]: Protocol Initiation: MARGIN_SET + SHOPIFY_PUBLISH")
        try:
            set_margin_and_publish(product_id, margin=0.3)
            _log(f"✅ [SYSTEM_LOG]: 30% margin set and publish triggered for {product_id}")
        except Exception as pub_err:
            _log(f"⚠️ [SYSTEM_WARNING]: Margin/publish failed: {pub_err}. Continuing with lifestyle.")
        
        # 5. Lifestyle Realization Step (runs while Printify syncs to Shopify)
        _log("[SYSTEM_LOG]: Protocol Initiation: LIFESTYLE_REALIZATION")
        
        # We need to RE-FETCH the product to get the mockups generated by Printify after cloning
        time.sleep(5)  # Brief pause for Printify to initialize the specimen
        product = fab.get_product(product_id)
        images = product.get('images', [])
        
        # Track lifestyle state for graceful failure handling
        lifestyle_path = None
        lifestyle_media_id = None
        lifestyle_src_url = None
        mockup_folder = None
        
        if images:
            # Look for 'front' mockup specifically if possible, else default to first
            mockup_url = images[0].get('src')
            for img in images:
                if 'front' in img.get('variant_ids', []) or 'front' in img.get('src', '').lower():
                    mockup_url = img.get('src')
                    break
                    
            lifestyle_path = synthesize_lifestyle_mockup(display_theme, product_title, mockup_url, blueprint_meta=blueprint_meta)
            
            if lifestyle_path:
                # [REMIX_PROTOCOL]: Apply STATUS: UNVERIFIED stamp as final layer
                apply_unverified_stamp(lifestyle_path)
                _log("[SYSTEM_LOG]: Lifestyle artifact stabilized. Injecting into Conduit...")
                # Ensure the file exists before upload
                if os.path.exists(lifestyle_path):
                    # [SIGNAL_RECOVERY]: Re-check file integrity and ensure binary read if needed
                    file_size = os.path.getsize(lifestyle_path)
                    _log(f"// UPLOADING_LIFESTYLE: {lifestyle_path} ({file_size} bytes)")
                    
                    # Printify upload ritual
                    lifestyle_media_id = fab.upload_image(local_path=lifestyle_path, file_name=f"lifestyle_{product_id}.png")
                    # Capture the src URL immediately — upload_image sets last_upload_src
                    lifestyle_src_url = fab.last_upload_src
                    
                    if lifestyle_media_id:
                        _log(f"// ARTIFACT_SECURED: ID_{lifestyle_media_id}")
                        _log(f"// LIFESTYLE_CDN: {lifestyle_src_url}")
                        
                        # [SYSTEM_NOTE]: Printify product gallery only accepts auto-generated mockups.
                        # Lifestyle image is archived locally with CDN URL for use in external channels.
                        _log(f"✅ [SYSTEM_SUCCESS]: Lifestyle mockup realized for {product_id}.")
                        
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
                        _log(f"✅ [SYSTEM_LOG]: Linkage secured: {mapping_file}")
                        
                        # [PROTOCOL_UPDATE]: Rename mockup folder to include product ID
                        old_folder = Path(lifestyle_path).parent
                        new_folder_name = f"{old_folder.name}__{product_id}"
                        new_folder = old_folder.parent / new_folder_name
                        try:
                            old_folder.rename(new_folder)
                            mockup_folder = str(new_folder)
                            _log(f"// FOLDER_RENAMED: {new_folder_name}")
                        except Exception as rename_err:
                            _log(f"!! [WARNING]: Folder rename failed: {rename_err}")
                            mockup_folder = str(old_folder)
                        
                        # 5. Wait for Shopify sync + Upload lifestyle to Shopify
                        _log("[SYSTEM_LOG]: Protocol Initiation: SHOPIFY_SYNC_WAIT")
                        try:
                            pub_shop_id = get_printify_shop_id() or fab.shop_id
                            shopify_product_id = wait_for_printify_publish(pub_shop_id, product_id)
                            if not shopify_product_id:
                                raise RuntimeError("Printify sync completed but no Shopify external ID returned.")
                            _log(f"[SYSTEM_LOG]: Printify→Shopify sync complete. Shopify product ID: {shopify_product_id}")
                            # Use the local lifestyle path for Shopify upload
                            resolved_lifestyle = str(Path(mockup_folder) / Path(lifestyle_path).name) if mockup_folder else lifestyle_path
                            upload_lifestyle_image(shopify_product_id, resolved_lifestyle)
                            _log(f"✅ [SYSTEM_SUCCESS]: Lifestyle image uploaded to Shopify product {shopify_product_id}")
                            
                            # [METADATA_THREAD]: Set Shopify product_type from blueprint metadata
                            # Tags are set on the Printify product and sync automatically via publish.
                            if blueprint_meta and blueprint_meta.get('product_type'):
                                try:
                                    from agents.skills.shopify_skill import ShopifyConduit
                                    conduit = ShopifyConduit()
                                    conduit.update_product(int(shopify_product_id), {
                                        "product_type": blueprint_meta['product_type'],
                                    })
                                    _log(f"✅ [SYSTEM_SUCCESS]: Shopify product_type set: {blueprint_meta['product_type']}")
                                except Exception as tag_err:
                                    _log(f"⚠️ [SYSTEM_WARNING]: Shopify product_type update failed: {tag_err}")
                            
                        except Exception as sync_err:
                            _log(f"⚠️ [SYSTEM_WARNING]: Shopify sync/upload failed: {sync_err}. Product still on Printify.")
                    else:
                        _log(f"❌ [SYSTEM_ERROR]: Media upload failed to return ID. Skipping Shopify image upload.")
                else:
                    _log(f"❌ [SYSTEM_ERROR]: Lifestyle path {lifestyle_path} not found. Skipping Shopify image upload.")
            else:
                _log(f"❌ [SYSTEM_ERROR]: Lifestyle synthesis failed. Skipping Shopify image upload.")
        else:
            _log(f"⚠️ [SYSTEM_WARNING]: No product images found for lifestyle synthesis. Skipping Shopify image upload.")
        
        _log(f"CONDUIT: https://printify.com/app/store/{fab.shop_id}/products/{product_id}")
        return product
    except Exception as e:
        _log(f"[SYSTEM_ERROR]: Realization failed: {e}")
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
    parser.add_argument("--tile-scale", type=float, default=1.0, help="Tile pattern scale (default: 1.0). Larger = bigger tiles, more detail visible.")
    
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
            tile_scale=args.tile_scale,
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
        tile_scale=args.tile_scale,
    )
