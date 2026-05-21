#!/usr/bin/env python3
"""
/* [FILE_ID]: veo_gen // VERSION: 1.0 // STATUS: STABLE */

VEO GEN — Ad-Hoc TikTok Video Synthesis
=========================================
Generates a 9:16 TikTok advertisement video from a Printify product's
flat mockup images using Google Veo via the Gemini API.

Design Principles:
  - Input is a Printify/Specimen product ID, not a raw image path.
  - Prefers flat, white-background mockup images from Printify's own
    rendered images — NOT lifestyle shots — so the product itself drives
    the visual anchor while Veo has creative latitude over atmosphere.
  - Gracefully omits the goose topology-lock modifier if the product is
    unverified (QR-stamp variant) — Veo has the most difficulty with the
    goose graphic, so the lock is only applied when genuinely needed.
  - Dry-run mode shows the assembled prompt and estimated cost before
    any API call is made.

Usage:
    python3 tools/veo_gen.py --product-id <PRINTIFY_PRODUCT_ID>
    python3 tools/veo_gen.py --product-id <PRINTIFY_PRODUCT_ID> --dry-run
    python3 tools/veo_gen.py --product-id <PRINTIFY_PRODUCT_ID> --model veo-3.1-lite
    python3 tools/veo_gen.py --product-id <PRINTIFY_PRODUCT_ID> --duration 6 --out-dir ./output
"""

import argparse
import os
import random
import re
import sys
import time
from pathlib import Path

import requests as _requests

# ── Path bootstrap ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / ".env")

from scripts.printify_markup import get_printify_api_key, get_product, get_shop_id
from agents.skills.fabricator.fabricator import parse_blueprint_metadata

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL       = "veo-3.1-generate-preview"
FALLBACK_MODEL      = "veo-3.1-lite"
ASPECT_RATIO        = "9:16"
DEFAULT_DURATION    = 8          # seconds
COST_PER_SECOND_LOW = 0.30
COST_PER_SECOND_HI  = 0.75
POLL_INTERVAL       = 15         # seconds between status checks

# ── Verified-product detection ─────────────────────────────────────────────────
# Verified specimens are renamed to the canonical "CBG Studio | <Name> ..." form.
# Unverified ones retain the "UNVERIFIED SPECIMEN" prefix and carry a QR stamp
# instead of the green goose logo.
_UNVERIFIED_PATTERN = re.compile(r"UNVERIFIED", re.IGNORECASE)

def has_goose_logo(product: dict) -> bool:
    """Return True if the product is verified (has goose logo, not QR stamp)."""
    title = product.get("title", "")
    return not _UNVERIFIED_PATTERN.search(title)


def extract_sizes(product: dict) -> list[str]:
    """Return the list of available size titles from a Printify product's options."""
    for opt in product.get("options", []):
        if opt.get("type", "").lower() in ("size", "sizes"):
            return [v["title"] for v in opt.get("values", []) if v.get("title")]
    return []


def get_blueprint_meta(product: dict) -> dict:
    """
    Fetch the Printify catalog blueprint title and parse gender/garment/model
    using the same parse_blueprint_metadata logic as verify_specimen.
    Falls back to empty dict on failure.
    """
    blueprint_id = product.get("blueprint_id")
    if not blueprint_id:
        return {}
    try:
        api_key = get_printify_api_key()
        url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}.json"
        resp = _requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        resp.raise_for_status()
        bp_title = resp.json().get("title", "")
        return parse_blueprint_metadata(bp_title)
    except Exception as exc:
        print(f"[SYSTEM_WARNING]: Could not fetch blueprint metadata — {exc}")
        return {}

# ── Image selection ────────────────────────────────────────────────────────────
def _camera_label(img: dict) -> str:
    src = img.get("src", "")
    # camera_label is embedded as a query param, e.g. ?camera_label=person-front
    if "camera_label=" in src:
        return src.split("camera_label=")[-1].split("&")[0]
    return img.get("position", "unknown")


def select_reference_images(
    product: dict,
) -> tuple[str, str | None, str | None, str | None]:
    """
    Return (flat_front_url, person_front_url, flat_back_url, person_back_url)
    from Printify's image array.

    Printify camera_label values observed:
      front / back               — flat product on white/neutral BG  (print anchor)
      person-front / person-back — on-body lifestyle shot            (fit/silhouette anchor)

    Priority:
      flat_front   — camera_label=front, or is_default, or first image.
      person_front — camera_label=person-front if present, else None.
      flat_back    — camera_label=back if present, else None.
      person_back  — camera_label=person-back if present, else None.
    """
    images = product.get("images", [])
    if not images:
        raise ValueError("[SIGNAL_LOSS]: No images found on this product.")

    flat_front: str | None = None
    person_front: str | None = None
    flat_back: str | None = None
    person_back: str | None = None

    for img in images:
        label = _camera_label(img)
        if label == "front" and flat_front is None:
            flat_front = img["src"]
        if label == "person-front" and person_front is None:
            person_front = img["src"]
        if label == "back" and flat_back is None:
            flat_back = img["src"]
        if label == "person-back" and person_back is None:
            person_back = img["src"]

    # Fallbacks for flat_front
    if flat_front is None:
        for img in images:
            if img.get("is_default"):
                flat_front = img["src"]
                break
    if flat_front is None:
        flat_front = images[0]["src"]

    return flat_front, person_front, flat_back, person_back

def fetch_image_bytes(url: str) -> bytes:
    """Download an image from a URL and return raw bytes."""
    resp = _requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _mime(url: str) -> str:
    return "image/jpeg" if url.lower().split("?")[0].endswith((".jpg", ".jpeg")) else "image/png"

# ── Prompt assembly ────────────────────────────────────────────────────────────
_ENVIRONMENTS = [
    "a rain-slicked city street at night, reflections of neon signs pooling on wet asphalt",
    "a brutalist concrete plaza — raw aggregate surfaces, hard shadows, overcast sky",
    "a dark void studio — pure black negative space with a single dramatic key light",
    "an overgrown infrastructure site — cracked concrete, encroaching foliage, diffused natural light",
    "a rooftop at dusk — city sprawl below, golden-hour light bleeding into deep shadow",
    "a decommissioned server room — floors of dead rack units, cold blue emergency lighting",
    "a rain-soaked underpass — layered graffiti, sodium-vapour glow, shallow puddles",
    "a brutalist stairwell — repeating geometric concrete, stark overhead fluorescents",
]

# Weighted mood pool — heavier toward varied/light moods so the feed doesn't
# read as uniformly threatening. Each entry is (mood_description, weight).
_MOODS: list[tuple[str, int]] = [
    # light / welcoming
    ("visibly happy and relaxed, a natural smile, at ease in the environment", 3),
    ("playful and flirty — a knowing look at camera, slight smirk, confident body language", 3),
    ("carefree and energetic, mid-movement as if caught dancing or spinning", 3),
    ("excited and expressive — wide grin, animated gesture, full of forward momentum", 2),
    # neutral / editorial
    ("composed and self-assured — calm, neutral expression, deliberate stance", 2),
    ("introspective — gazing off-frame, relaxed, quietly present in the space", 2),
    # serious / intense (still available but not dominant)
    ("focused and intense — sharp gaze, still, commanding the space", 1),
    ("cool and detached — unreadable expression, effortless stillness", 1),
]

def _pick_environment() -> str:
    return random.choice(_ENVIRONMENTS)

def _pick_mood() -> str:
    moods, weights = zip(*_MOODS)
    return random.choices(moods, weights=weights, k=1)[0]

_BASE_ATMOSPHERE_TEMPLATE = (
    "A cinematic, high-fidelity product advertisement for an Industrial Noir × Tech-Wear garment. "
    "Environment: {environment}. "
    "Subject: {subject}. "
    "Subject mood and energy: {mood}. "
    "The visual narrative should feel raw, sovereign, and high-signal. "
    "Structure the shot sequence exactly as follows: "
    "SHOT 1 — Wide establishing shot of the subject from the FRONT: full silhouette visible, "
    "garment front print fully readable, mood clearly expressed, environment in frame. "
    "SHOT 2 — Close-up lateral pan across the FRONT of the garment: slow, stable pan revealing "
    "print detail, texture, and colour field — treat the fabric surface like a landscape being surveyed. "
    "SHOT 3 — Close-up lateral pan across the BACK of the garment: same slow, deliberate pan "
    "to reveal the back print detail, then pull back to a mid-distance shot showing the full back of the wearer. "
    "SHOT 4 — Wide shot of the subject from the BACK: full back silhouette, garment back print visible, "
    "subject still in the same environment and mood. "
    "No zooming at any point. All camera movements must be slow, stable pans or tracking shots. "
    "No rapid cuts or shaky motion. "
    "The print artwork on the garment — both front and back — must remain sharp and undistorted in every frame."
)

# Unified garment fidelity block — enforces print accuracy, silhouette/length
# preservation, and logo avoidance in a single coherent instruction so Veo
# doesn't receive competing focal cues that cause it to zoom into the goose.
_GARMENT_FIDELITY_LOCK = (
    "GARMENT FIDELITY RULES (apply throughout every frame): "
    "1) Print & graphics: all artwork on the garment is a static texture map — "
    "it must not morph, blur, smear, or animate. Reproduce every colour and line exactly. "
    "2) Logo / emblem avoidance: the garment may contain logos, emblems, or illustrated figures "
    "as part of its all-over print — treat ALL of these as flat, passive surface texture, not as "
    "subjects or focal points. The camera must NEVER zoom toward, frame, or linger on any "
    "logo or illustrated element. Camera movement across the print must be a slow, even lateral pan "
    "that treats the entire fabric surface uniformly — no drifting toward or locking onto any graphic detail. "
    "3) Silhouette & length: the garment's cut, hemline, and proportions must be "
    "pixel-identical to the reference image in every frame — do not lengthen, shorten, "
    "or alter the silhouette."
)

# Keep individual constants for backward-compatibility / future selective use
_TOPOLOGY_LOCK = _GARMENT_FIDELITY_LOCK  # alias
_LENGTH_LOCK = _GARMENT_FIDELITY_LOCK    # alias

# Garment types where Veo tends to hallucinate length — skirts get lengthened,
# shorts get turned into long pants, etc. Detected from blueprint garment name.
_LENGTH_SENSITIVE_KEYWORDS = (
    "skirt", "shorts", "short", "dress", "mini", "midi", "maxi",
    "leggings", "legging", "pants", "trousers", "jogger",
)

_LENGTH_LOCK = (
    "CRITICAL: Preserve the exact garment length and silhouette as shown in the reference image — "
    "do not lengthen, shorten, or alter the hemline. "
    "The garment's cut and proportions must remain identical to the reference throughout every frame."
)


def _garment_needs_length_lock(garment: str) -> bool:
    """Return True if the garment type is known to cause length hallucination."""
    g = garment.lower()
    return any(kw in g for kw in _LENGTH_SENSITIVE_KEYWORDS)


# Maps Printify size labels to body-type descriptors Veo can actually use.
# Avoids passing raw size strings ("XL", "2XL") which Veo interprets as height/stature.
# Descriptors are intentionally realistic and inclusive — not fashion-model defaults.
_SIZE_TO_BODY_TYPE: dict[str, str] = {
    "XS":  "a petite, slender build",
    "S":   "a slim, average-height build",
    "M":   "an average, mid-size build",
    "L":   "a fuller, athletic build",
    "XL":  "a curvy, plus-size build",
    "2XL": "a full-figured, plus-size build",
    "3XL": "a full-figured, plus-size build",
    "4XL": "a full-figured, plus-size build",
}


def _size_to_body_descriptor(size: str | None) -> str | None:
    """Return a body-type description for a given size label, or None if unmapped."""
    if not size:
        return None
    return _SIZE_TO_BODY_TYPE.get(size.upper())


def _build_subject(blueprint_meta: dict, sizes: list[str], ethnicity: str | None = None) -> str:
    """
    Build a subject descriptor from blueprint gender, ethnicity override, and
    a size-mapped body-type description.
    Size labels are mapped to body-type descriptors (e.g. XL → "curvy, plus-size build")
    so Veo represents real body diversity instead of defaulting to thin fashion models.
    """
    if ethnicity:
        base = ethnicity  # e.g. "a Black female model"
    else:
        base = blueprint_meta.get("model", "a model")

    size = (sizes[0] if len(sizes) == 1 else random.choice(sizes)) if sizes else None
    body = _size_to_body_descriptor(size)
    if body:
        return f"{base} with {body}"
    return base


def build_prompt(
    product: dict,
    goose: bool,
    has_person_ref: bool = True,
    has_back_ref: bool = False,
    blueprint_meta: dict | None = None,
    sizes: list[str] | None = None,
    ethnicity: str | None = None,
    override_environment: str | None = None,
    override_mood: str | None = None,
) -> tuple[str, str, str, str]:
    """Returns (prompt, environment_label, mood_label, subject_label)."""
    product_title = product.get("title", "CBG Studio product")
    # Strip the canonical prefix for a cleaner description
    clean_title = re.sub(r"^CBG Studio \| ", "", product_title, flags=re.IGNORECASE)
    clean_title = re.sub(r"\| SPECIMEN:.*$", "", clean_title).strip()

    environment = override_environment or _pick_environment()
    mood = override_mood or _pick_mood()
    subject = _build_subject(blueprint_meta or {}, sizes or [], ethnicity=ethnicity)
    atmosphere = _BASE_ATMOSPHERE_TEMPLATE.format(environment=environment, mood=mood, subject=subject)

    parts = [f"Product: {clean_title}."]

    if has_person_ref and has_back_ref:
        parts.append(
            "Four reference images are provided: "
            "[1] the garment worn on a person from the FRONT — preserve that exact person, "
            "their body type, and how the garment fits them; "
            "[2] the isolated garment FRONT on a neutral background — print and colour fidelity reference; "
            "[3] the garment worn on a person from the BACK — use for back silhouette and fit reference; "
            "[4] the isolated garment BACK on a neutral background — back print fidelity reference. "
            "Transport the person into the new environment described below; "
            "do not carry over the original background, lighting, or any other garments or accessories."
        )
    elif has_person_ref:
        parts.append(
            "Two reference images are provided: "
            "[1] the garment worn on a person from the FRONT — preserve that exact person, "
            "their body type, and how the garment fits them. "
            "Transport them into the new environment described below; "
            "do not carry over the original background, lighting, or any other garments or accessories. "
            "[2] the isolated garment on a neutral background — print and colour fidelity reference only."
        )
    else:
        parts.append(
            "A reference image of the isolated garment on a neutral background is provided — "
            "use it to faithfully reproduce the garment's exact print, colour, and structure."
        )

    parts.append(atmosphere)

    # Always append — covers print fidelity, logo avoidance, and silhouette lock
    parts.append(_GARMENT_FIDELITY_LOCK)

    return " ".join(parts), environment, mood, subject

# ── Veo generation ─────────────────────────────────────────────────────────────
def generate_video(
    *,
    model: str,
    prompt: str,
    flat_bytes: bytes,
    flat_mime: str,
    person_bytes: bytes | None,
    person_mime: str | None,
    flat_back_bytes: bytes | None = None,
    flat_back_mime: str | None = None,
    person_back_bytes: bytes | None = None,
    person_back_mime: str | None = None,
    duration: int,
    dry_run: bool,
    out_path: Path,
) -> None:
    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        print(
            "[SIGNAL_LOSS]: google-genai is not installed.\n"
            "  Install with:  pip install google-genai"
        )
        sys.exit(1)

    api_key = os.getenv("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[SIGNAL_LOSS]: gemini_api_key not found in .env")
        sys.exit(1)

    # ── Cost estimate ──────────────────────────────────────────────────────────
    cost_low  = duration * COST_PER_SECOND_LOW
    cost_high = duration * COST_PER_SECOND_HI
    print()
    print("═" * 60)
    print(f"  [SYSTEM_LOG]: MODEL    → {model}")
    print(f"  [SYSTEM_LOG]: DURATION → {duration}s")
    print(f"  [SYSTEM_LOG]: COST EST → ${cost_low:.2f} – ${cost_high:.2f}")
    print(f"  [SYSTEM_LOG]: OUTPUT   → {out_path}")
    print("═" * 60)
    print()
    print("[ASSEMBLED PROMPT]")
    print(prompt)
    print()

    if dry_run:
        print("[DRY_RUN]: No API call made. Remove --dry-run to execute.")
        return

    confirm = input(f"Proceed with generation? Estimated cost: ${cost_low:.2f}–${cost_high:.2f}  [y/N] ").strip().lower()
    if confirm != "y":
        print("[ABORTED]: Operation cancelled by Specialist.")
        sys.exit(0)

    # ── API call ───────────────────────────────────────────────────────────────
    client = genai.Client(api_key=api_key)

    print(f"\n[SYSTEM_LOG]: Initiating Veo generation via {model} …")

    # Build reference image list (up to 4 angles):
    #   [0] ASSET — person-front on-body shot: anchors person, fit, and silhouette
    #   [1] ASSET — flat-front isolated product: front print + colour fidelity reference
    #   [2] ASSET — person-back on-body shot (if available): back silhouette reference
    #   [3] ASSET — flat-back isolated product (if available): back print fidelity reference
    def _ref(img_bytes: bytes, mime: str) -> gtypes.VideoGenerationReferenceImage:
        return gtypes.VideoGenerationReferenceImage(
            image=gtypes.Image(image_bytes=img_bytes, mime_type=mime),
            reference_type=gtypes.VideoGenerationReferenceType.ASSET,
        )

    ref_images = []
    if person_bytes is not None:
        ref_images.append(_ref(person_bytes, person_mime))
    ref_images.append(_ref(flat_bytes, flat_mime))
    if person_back_bytes is not None:
        ref_images.append(_ref(person_back_bytes, person_back_mime))
    if flat_back_bytes is not None:
        ref_images.append(_ref(flat_back_bytes, flat_back_mime))
    print(f"[SYSTEM_LOG]: Reference images → {len(ref_images)} angle(s) provided.")

    operation = client.models.generate_videos(
        model=model,
        prompt=prompt,
        config=gtypes.GenerateVideosConfig(
            aspect_ratio=ASPECT_RATIO,
            number_of_videos=1,
            duration_seconds=duration,
            reference_images=ref_images,
        ),
    )

    # ── Poll ───────────────────────────────────────────────────────────────────
    print(f"[SYSTEM_LOG]: Operation submitted. Polling every {POLL_INTERVAL}s …")
    while not operation.done:
        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)
        print(f"  … still processing ({operation.name})")

    # ── Save ───────────────────────────────────────────────────────────────────
    if operation.result and operation.result.generated_videos:
        video = operation.result.generated_videos[0].video
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if video.video_bytes:
            out_path.write_bytes(video.video_bytes)
            print(f"\n[SYSTEM_SUCCESS]: Video saved → {out_path}")
        elif video.uri:
            # Veo returns a Files API URI — must authenticate with the API key.
            print(f"[SYSTEM_LOG]: Received Files API URI — downloading …")
            download_url = video.uri
            if "?" in download_url:
                download_url += f"&key={api_key}"
            else:
                download_url += f"?key={api_key}"
            vid_resp = _requests.get(download_url, timeout=120)
            vid_resp.raise_for_status()
            out_path.write_bytes(vid_resp.content)
            print(f"\n[SYSTEM_SUCCESS]: Video saved → {out_path}")
        else:
            print("[SIGNAL_LOSS]: Generation completed but video has no bytes or URI.")
            sys.exit(1)
    else:
        print("[SIGNAL_LOSS]: Generation completed but no video was returned.")
        print(f"  Raw result: {operation.result}")
        sys.exit(1)

# ── CLI ────────────────────────────────────────────────────────────────────────
def prompt_overrides(
    blueprint_meta: dict,
    sizes: list[str],
    default_environment: str,
    default_mood: str,
    default_size: str | None,
) -> dict:
    """
    Interactively present detected defaults and allow the Specialist to
    override gender, size, environment, and mood before generation.
    Mirrors the override UX in verify_specimen.py.
    Returns dict with keys: gender, model, size, environment, mood.
    """
    gender   = blueprint_meta.get("gender", "unisex")
    model    = blueprint_meta.get("model", "a model")
    size     = default_size
    env      = default_environment
    mood     = default_mood

    print()
    print("─" * 60)
    print("[VEO_OVERRIDE]: Press Enter to keep each default, or select an option.")
    print("─" * 60)

    # ── GENDER ──────────────────────────────────────────────────────────────
    gender_label = {"women": "Female", "men": "Male", "unisex": "Unisex"}.get(gender, "Unisex")
    print(f"\n  Gender       : {gender_label} (detected)")
    print("                 [F] Female  [M] Male  [U] Unisex  [Enter] keep")
    choice = input("  → ").strip().lower()
    GENDER_MAP = {
        "f": ("women",  "a female model"),
        "m": ("men",    "a male model"),
        "u": ("unisex", "a model"),
    }
    if choice in GENDER_MAP:
        gender, model = GENDER_MAP[choice]

    # ── SIZE ─────────────────────────────────────────────────────────────────
    default_body = _size_to_body_descriptor(size) or "random"
    print(f"\n  Body type    : {size or 'random'} → {default_body}")
    print("  (Sizes map to body-type descriptors; choose to influence body representation)")
    if sizes:
        for i, s in enumerate(sizes, 1):
            body_desc = _size_to_body_descriptor(s) or s
            marker = " ← current" if s == size else ""
            print(f"    [{i}] {s:5s} → {body_desc}{marker}")
        print("    [Enter] keep current")
        choice = input("  → ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(sizes):
                size = sizes[idx]

    # ── ENVIRONMENT ──────────────────────────────────────────────────────────
    print(f"\n  Environment  : {env}")
    print("  (default: randomly selected — listed below)")
    for i, e in enumerate(_ENVIRONMENTS, 1):
        marker = " ← current" if e == env else ""
        print(f"    [{i}] {e}{marker}")
    print("    [Enter] keep current")
    choice = input("  → ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(_ENVIRONMENTS):
            env = _ENVIRONMENTS[idx]

    # ── MOOD ─────────────────────────────────────────────────────────────────
    mood_labels = [m for m, _ in _MOODS]
    print(f"\n  Mood         : {mood}")
    print("  (default: weighted random — listed below)")
    for i, (m, w) in enumerate(_MOODS, 1):
        marker = " ← current" if m == mood else ""
        print(f"    [{i}] {m}  (weight {w}){marker}")
    print("    [Enter] keep current")
    choice = input("  → ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(_MOODS):
            mood = _MOODS[idx][0]

    # ── ETHNICITY ──────────────────────────────────────────────────────────
    ETHNICITIES = [
        ("1", "not specified (model decides)",        None),
        ("2", "Black / African",                      "a Black {g} model"),
        ("3", "Latina / Hispanic",                    "a Latina {g} model"),
        ("4", "South Asian",                          "a South Asian {g} model"),
        ("5", "East Asian",                           "an East Asian {g} model"),
        ("6", "Middle Eastern / North African",       "a Middle Eastern {g} model"),
        ("7", "Indigenous / Native",                  "an Indigenous {g} model"),
        ("8", "Mixed / multiracial",                  "a mixed-race {g} model"),
        ("9", "White / European",                     "a White {g} model"),
    ]
    gender_adj = {"women": "female", "men": "male", "unisex": ""}.get(gender, "")
    ethnicity: str | None = None
    print("\n  Ethnicity    : not specified (default)")
    for key, label, _ in ETHNICITIES:
        marker = " ← default" if key == "1" else ""
        print(f"    [{key}] {label}{marker}")
    choice = input("  → ").strip()
    for key, _, tmpl in ETHNICITIES:
        if choice == key:
            ethnicity = tmpl.replace("{g}", gender_adj).strip() if tmpl else None
            break

    print("─" * 60)
    return {"gender": gender, "model": model, "ethnicity": ethnicity, "size": size, "environment": env, "mood": mood}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="[VEO_GEN] Generate a TikTok ad video from a Printify product."
    )
    parser.add_argument(
        "--product-id",
        required=True,
        metavar="PRINTIFY_ID",
        help="Printify product ID (same as the Specimen ID used in verify_specimen.py).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=[DEFAULT_MODEL, FALLBACK_MODEL],
        help=f"Veo model to use. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        metavar="SECONDS",
        help=f"Video duration in seconds. Default: {DEFAULT_DURATION}",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "artifacts" / "generated" / "veo",
        metavar="PATH",
        help="Output directory for the generated .mp4 file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble and display the prompt + cost estimate without making an API call.",
    )
    parser.add_argument(
        "--no-override",
        action="store_true",
        help="Skip the interactive override prompts and use all random defaults.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── Fetch product ──────────────────────────────────────────────────────────
    print(f"[SYSTEM_LOG]: Fetching product {args.product_id} from Printify …")
    try:
        shop_id = get_shop_id()
        product = get_product(shop_id, args.product_id)
    except Exception as exc:
        print(f"[SIGNAL_LOSS]: Failed to fetch product — {exc}")
        sys.exit(1)

    product_title = product.get("title", args.product_id)
    print(f"[SYSTEM_LOG]: Product → {product_title}")

    # ── Select images ──────────────────────────────────────────────────────────
    flat_url, person_url, flat_back_url, person_back_url = select_reference_images(product)
    print(f"[SYSTEM_LOG]: Flat front   → {flat_url[:90]}…")
    if person_url:
        print(f"[SYSTEM_LOG]: Person front → {person_url[:90]}… [PRIMARY]")
    else:
        print("[SYSTEM_LOG]: No person-front image found — using flat reference only.")
    if flat_back_url:
        print(f"[SYSTEM_LOG]: Flat back    → {flat_back_url[:90]}…")
    else:
        print("[SYSTEM_LOG]: No flat-back image found.")
    if person_back_url:
        print(f"[SYSTEM_LOG]: Person back  → {person_back_url[:90]}…")
    else:
        print("[SYSTEM_LOG]: No person-back image found.")

    # ── Goose detection ────────────────────────────────────────────────────────
    goose = has_goose_logo(product)
    if goose:
        print("[SYSTEM_LOG]: Goose logo detected — topology lock modifier ACTIVE.")
    else:
        print("[SYSTEM_LOG]: QR-stamp variant (unverified) — topology lock modifier SKIPPED.")

    # ── Blueprint meta + sizes ─────────────────────────────────────────────────
    blueprint_meta = get_blueprint_meta(product)
    sizes = extract_sizes(product)
    print(f"[SYSTEM_LOG]: Blueprint   → gender={blueprint_meta.get('gender','?')} garment={blueprint_meta.get('garment','?')}")
    print(f"[SYSTEM_LOG]: Sizes avail → {sizes}")

    # Pick initial random defaults so they can be shown in the override menu
    default_env  = _pick_environment()
    default_mood = _pick_mood()
    default_size = random.choice(sizes) if sizes else None

    # ── Interactive overrides ──────────────────────────────────────────────────
    if not args.no_override:
        overrides = prompt_overrides(
            blueprint_meta, sizes, default_env, default_mood, default_size
        )
        blueprint_meta = dict(blueprint_meta)
        blueprint_meta["gender"] = overrides["gender"]
        blueprint_meta["model"]  = overrides["model"]
        final_ethnicity = overrides["ethnicity"]
        final_size  = overrides["size"]
        final_env   = overrides["environment"]
        final_mood  = overrides["mood"]
    else:
        final_ethnicity = None
        final_size  = default_size
        final_env   = default_env
        final_mood  = default_mood

    # ── Build prompt ───────────────────────────────────────────────────────────
    prompt, environment, mood, subject = build_prompt(
        product, goose,
        has_person_ref=person_url is not None,
        has_back_ref=(flat_back_url is not None or person_back_url is not None),
        blueprint_meta=blueprint_meta,
        sizes=[final_size] if final_size else [],
        ethnicity=final_ethnicity,
        override_environment=final_env,
        override_mood=final_mood,
    )
    print(f"[SYSTEM_LOG]: Subject     → {subject}")
    print(f"[SYSTEM_LOG]: Environment → {environment}")
    print(f"[SYSTEM_LOG]: Mood        → {mood}")

    # ── Resolve output path ────────────────────────────────────────────────────
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", args.product_id)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = args.out_dir / f"{safe_id}_{ts}.mp4"

    # ── Fetch image bytes (skip in dry-run to avoid latency) ───────────────────
    if not args.dry_run:
        print("[SYSTEM_LOG]: Downloading reference images …")
        try:
            flat_bytes = fetch_image_bytes(flat_url)
            person_bytes = fetch_image_bytes(person_url) if person_url else None
            flat_back_bytes = fetch_image_bytes(flat_back_url) if flat_back_url else None
            person_back_bytes = fetch_image_bytes(person_back_url) if person_back_url else None
        except Exception as exc:
            print(f"[SIGNAL_LOSS]: Could not download image — {exc}")
            sys.exit(1)
    else:
        flat_bytes = b""
        person_bytes = None
        flat_back_bytes = None
        person_back_bytes = None

    # ── Generate ───────────────────────────────────────────────────────────────
    generate_video(
        model=args.model,
        prompt=prompt,
        flat_bytes=flat_bytes,
        flat_mime=_mime(flat_url),
        person_bytes=person_bytes,
        person_mime=_mime(person_url) if person_url else None,
        flat_back_bytes=flat_back_bytes,
        flat_back_mime=_mime(flat_back_url) if flat_back_url else None,
        person_back_bytes=person_back_bytes,
        person_back_mime=_mime(person_back_url) if person_back_url else None,
        duration=args.duration,
        dry_run=args.dry_run,
        out_path=out_path,
    )


if __name__ == "__main__":
    main()
