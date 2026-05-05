#!/usr/bin/env python3
"""
/* [FILE_ID]: verify_specimen // VERSION: 1.0 // STATUS: STABLE */

VERIFY SPECIMEN — The Curation Ritual
======================================
Transitions an UNVERIFIED SPECIMEN into a verified, branded product.

What it does:
  1. Fetches the Printify product and its Shopify counterpart.
  2. Parses the description prefix (before ':') to derive the new product name.
  3. Determines product_type (from Shopify or via blueprint inference).
  4. Builds the new canonical title and validates its length.
  5. Replaces the QR-code stamp with the green goose logo in Printify print areas.
  6. Renames the product on Printify and waits for Shopify sync.
  7. Synthesises a new lifestyle image (goose-stamped, not QR-stamped).
  8. Uploads the new lifestyle image to Shopify as the primary image.
  9. Updates the Shopify URL handle (removes 'unverified') and creates a redirect.

Usage:
    python3 scripts/verify_specimen.py <PRINTIFY_PRODUCT_ID>
    python3 scripts/verify_specimen.py <PRINTIFY_PRODUCT_ID> --dry-run
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

# ── Path bootstrap ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(dotenv_path=ROOT / ".env")

from agents.skills.fabricator.fabricator import Fabricator, parse_blueprint_metadata
from agents.skills.nanobanana_skill.nanobanana_skill import generate_nano_banana_image
from agents.skills.shopify_skill import ShopifyConduit
from scripts.fabricate_specimen_v2 import synthesize_lifestyle_mockup
from scripts.publish_printify_product import (
    get_printify_shop_id,
    wait_for_printify_publish,
    upload_lifestyle_image,
)
from scripts.printify_markup import get_product, get_printify_api_key, get_shop_id

# ── Constants ─────────────────────────────────────────────────────────────────
GOOSE_LOGO_PATH = ROOT / "artifacts/graphics/logos/green_goose.png"
MAX_TITLE_LENGTH = 255
PRINTIFY_API_BASE = "https://api.printify.com/v1"

# Standard Printify EU/GPSR compliance block — same for all Printify-fulfilled products.
# EU representative: HONSON VENTURES LIMITED (Printify's designated EU rep).
EU_SAFETY_INFORMATION = (
    "<p><strong>EU representative</strong>: HONSON VENTURES LIMITED, "
    "gpsr@honsonventures.com, 3, Gnaftis House flat 102, Limassol, "
    "Mesa Geitonia, 4003, CY</p>\n"
    "<p><strong>Product information</strong>: Generic brand, 2 year warranty "
    "in EU and Northern Ireland as per Directive 1999/44/EC</p>\n"
    "<p><strong>Care instructions</strong>: Do not dryclean, Do not iron, "
    "Do not tumble dry, Do not bleach, Machine wash: cold (max 30C or 90F)</p>"
)


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}")


# ── Printify helpers ──────────────────────────────────────────────────────────

def _printify_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_printify_api_key()}",
        "Content-Type": "application/json",
    }


def get_printify_product(shop_id: str, product_id: str) -> dict:
    url = f"{PRINTIFY_API_BASE}/shops/{shop_id}/products/{product_id}.json"
    resp = requests.get(url, headers=_printify_headers())
    resp.raise_for_status()
    return resp.json()


def update_printify_product(shop_id: str, product_id: str, payload: dict) -> dict:
    url = f"{PRINTIFY_API_BASE}/shops/{shop_id}/products/{product_id}.json"
    resp = requests.put(url, headers=_printify_headers(), json=payload)
    if not resp.ok:
        _log(f"[SYSTEM_ERROR]: Printify PUT {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def upload_image_to_printify(fab: Fabricator, local_path: str, file_name: str) -> str:
    """Upload a local image to Printify and return the new image ID."""
    return fab.upload_image(local_path=local_path, file_name=file_name)


# ── Shopify helpers ───────────────────────────────────────────────────────────

def get_shopify_product(conduit: ShopifyConduit, shopify_id: int) -> dict:
    return conduit.get_product(shopify_id)


def find_shopify_product_by_title_fragment(conduit: ShopifyConduit, fragment: str) -> dict | None:
    """Scan Shopify products for one whose title contains `fragment`."""
    products = conduit.list_products(limit=250)
    for p in products:
        if fragment in p.get("title", ""):
            return conduit.get_product(p["id"])
    return None


def extract_lore_names(title: str) -> list:
    """
    Parse lore theme names out of a product title.

    REMIX format:  '... REMIX [Theme One x Theme Two] ...'
      → ['Theme One', 'Theme Two']

    Single-lore:   'CBG Studio | System Failure 3 Aesthetics: ...'
      → ['System Failure']  (trailing numbers stripped)
    """
    # REMIX branch
    remix_match = re.search(r'\bREMIX\s+\[([^\]]+)\]', title)
    if remix_match:
        names = [n.strip() for n in remix_match.group(1).split(' x ')]
    else:
        # Single lore: text between '| ' and ' Aesthetics'
        single_match = re.search(r'CBG Studio \| (.+?) Aesthetics', title)
        if single_match:
            names = [single_match.group(1).strip()]
        else:
            return []
    # Strip trailing version numbers (e.g. 'System Failure 3' → 'System Failure')
    return [re.sub(r'\s+\d+\s*$', '', n).strip() for n in names]


def ensure_lore_collections(conduit: ShopifyConduit, title: str, dry_run: bool = False) -> None:
    """
    Check that a Shopify smart collection exists for each lore referenced in
    the product title, creating any that are missing.

    Collection title format: '[LORE NAME]'
    Smart rule: product title contains '<lore name lowercase>'
    """
    lore_names = extract_lore_names(title)
    if not lore_names:
        _log("[SYSTEM_WARNING]: Could not extract lore names from title — skipping collection check.")
        return

    _log(f"[SYSTEM_LOG]: Lore names for collection check: {lore_names}")

    existing = conduit.get_all_smart_collections()
    existing_titles = {c["title"].upper() for c in existing}

    for name in lore_names:
        col_title = f"[{name.upper()}]"
        if col_title in existing_titles:
            _log(f"[SYSTEM_LOG]: Collection already exists: {col_title!r} — no action needed.")
            continue

        filter_str = name.lower()
        if dry_run:
            _log(f"[DRY_RUN]: Would create smart collection {col_title!r} (title contains {filter_str!r}).")
            continue

        _log(f"[SYSTEM_LOG]: Creating smart collection {col_title!r} (title contains {filter_str!r})...")
        try:
            conduit.create_smart_collection(
                title=col_title,
                rules=[{"column": "title", "relation": "contains", "condition": filter_str}],
            )
            _log(f"[SYSTEM_LOG]: Smart collection created: {col_title!r}")
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Failed to create collection {col_title!r}: {e}")


def create_shopify_redirect(conduit: ShopifyConduit, from_path: str, to_path: str) -> dict:
    """Create a URL redirect in Shopify (from_path → to_path)."""
    redirect = conduit.create_redirect(from_path, to_path)
    _log(f"[SYSTEM_LOG]: Redirect created: {from_path} → {to_path} (id={redirect.get('id')})")
    return redirect


# ── Logo helpers ──────────────────────────────────────────────────────────────

def _resize_goose_to_match(goose_path: Path, target_size: tuple[int, int]) -> Image.Image:
    """Return the green goose logo resized to target_size (w, h)."""
    goose = Image.open(str(goose_path)).convert("RGBA")
    return goose.resize(target_size, Image.LANCZOS)


def apply_goose_stamp(image_path: str, goose_path: Path = GOOSE_LOGO_PATH) -> str:
    """
    Composites the green goose logo onto the image at the same size/position
    as the QR code stamp (bottom-right corner, ~12% of image width).
    Returns the same image_path (modified in-place).
    """
    if not goose_path.exists():
        _log(f"[SYSTEM_WARNING]: Goose logo not found at {goose_path}. Skipping stamp.")
        return image_path

    try:
        base_img = Image.open(image_path).convert("RGBA")
        stamp_size = max(int(base_img.width * 0.12), 48)
        goose = _resize_goose_to_match(goose_path, (stamp_size, stamp_size))
        padding = int(base_img.width * 0.03)
        x = base_img.width - stamp_size - padding
        y = base_img.height - stamp_size - padding
        base_img.paste(goose, (x, y), goose)
        base_img.save(image_path)
        _log(f"// GOOSE_STAMP_APPLIED @ ({x}, {y}) size={stamp_size}px")
        return image_path
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Goose stamp failed: {e}")
        return image_path


# ── Title helpers ─────────────────────────────────────────────────────────────

def parse_description_prefix(description: str) -> str | None:
    """
    Extract the text up to and including the ':' from the description.
    E.g. "CBG Studio | REMIX [Silicon Pulse x Circuit Overload 2]: ..." → "CBG Studio | REMIX [Silicon Pulse x Circuit Overload 2]"
    Returns None if no ':' found.
    """
    if not description:
        return None
    idx = description.find(":")
    if idx == -1:
        return None
    return description[:idx].strip()


def build_new_title(prefix: str, product_type: str, printify_id: str) -> str:
    """
    Constructs the verified specimen title:
    "{prefix} {product_type} | SPECIMEN: {printify_id}"
    """
    return f"{prefix} {product_type} | SPECIMEN: {printify_id}"


# ── Blueprint / product_type inference ───────────────────────────────────────

def fetch_blueprint_meta(product: dict) -> dict:
    """
    Fetch the Printify catalog blueprint title and parse it into a metadata dict
    (gender, garment, model, tags, product_type) using parse_blueprint_metadata.
    Returns {} on failure.
    """
    blueprint_id = product.get("blueprint_id")
    if not blueprint_id:
        return {}
    try:
        url = f"{PRINTIFY_API_BASE}/catalog/blueprints/{blueprint_id}.json"
        resp = requests.get(url, headers=_printify_headers())
        resp.raise_for_status()
        bp_title = resp.json().get("title", "")
        return parse_blueprint_metadata(bp_title)
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Failed to fetch blueprint metadata: {e}")
        return {}


def infer_product_type_from_printify(product: dict) -> str | None:
    """
    Derive the product_type string from Printify product data using
    the same parse_blueprint_metadata logic as the fabricator.
    """
    return fetch_blueprint_meta(product).get("product_type") or None


# ── QR → Goose swap in Printify print_areas ──────────────────────────────────

def _identify_logo_image_ids(product: dict) -> set[str]:
    """
    Re-implements the fabricator's role-detection logic on a live product's print_areas.
    Returns the set of Printify image IDs that are in the 'logo' role.
    """
    logo_ids = set()
    for area in product.get("print_areas", []):
        for ph in area.get("placeholders", []):
            pos = ph.get("position", "").lower()
            is_trim = any(t in pos for t in ("waistband", "trim", "collar", "cuff"))
            images = ph.get("images", [])
            has_tiled_bg = any("pattern" in img for img in images)
            for img in images:
                img_id = img.get("id")
                if not img_id:
                    continue
                if "pattern" in img:
                    continue  # tile, not logo
                if has_tiled_bg:
                    logo_ids.add(img_id)
                elif not is_trim and img.get("scale", 1.0) < 0.4:
                    logo_ids.add(img_id)
    return logo_ids


def _get_logo_image_sizes(product: dict, logo_ids: set[str]) -> dict[str, tuple[int, int]]:
    """
    For each logo image ID, look up its dimensions from the print_area placeholder images.
    Falls back to (256, 256) if not available.
    """
    sizes = {}
    for area in product.get("print_areas", []):
        for ph in area.get("placeholders", []):
            for img in ph.get("images", []):
                img_id = img.get("id")
                if img_id in logo_ids and img_id not in sizes:
                    w = img.get("width", 256)
                    h = img.get("height", 256)
                    sizes[img_id] = (w, h)
    # Fill any not found with fallback
    for lid in logo_ids:
        if lid not in sizes:
            sizes[lid] = (256, 256)
    return sizes


# Fields Printify accepts on image objects in a PUT payload.
# Read-only fields returned by GET (src, name, type, layerType, imageId, etc.) cause 400s.
_PRINTIFY_IMAGE_PUT_FIELDS = {"id", "x", "y", "scale", "angle", "flipX", "flipY", "pattern", "height", "width"}


def _clean_image_for_put(img: dict, override_id: str | None = None) -> dict:
    """Strip read-only fields from a Printify image object for use in PUT payloads."""
    out = {k: v for k, v in img.items() if k in _PRINTIFY_IMAGE_PUT_FIELDS}
    if override_id is not None:
        out["id"] = override_id
    return out


def build_verified_print_areas(product: dict, logo_ids: set[str], new_logo_id: str) -> list:
    """
    Clone the Printify product's print_areas, swapping all logo-role image IDs
    with the new goose logo image ID. Strips read-only fields so the payload is
    accepted by the Printify PUT endpoint.
    """
    new_print_areas = []
    for area in product.get("print_areas", []):
        new_placeholders = []
        for ph in area.get("placeholders", []):
            if not ph.get("images"):  # skip empty-image placeholders — Printify rejects them on PUT
                continue
            new_images = []
            for img in ph.get("images", []):
                if img.get("id") in logo_ids:
                    new_images.append(_clean_image_for_put(img, override_id=new_logo_id))
                else:
                    new_images.append(_clean_image_for_put(img))
            placeholder = {"position": ph.get("position"), "images": new_images}
            if ph.get("decoration_method"):
                placeholder["decoration_method"] = ph["decoration_method"]
            new_placeholders.append(placeholder)
        area_entry = {
            "variant_ids": area.get("variant_ids"),
            "placeholders": new_placeholders,
        }
        if area.get("background") is not None:
            area_entry["background"] = area["background"]
        new_print_areas.append(area_entry)
    return new_print_areas


# ── Local metadata recovery ───────────────────────────────────────────────────

def find_local_product_metadata(printify_id: str) -> dict | None:
    """
    Search the local catalog and mockup product_link.json files for metadata
    that can be used to recover missing description or product_type.
    """
    # 1. Check artifacts/catalog/products.json
    catalog_path = ROOT / "artifacts/catalog/products.json"
    if catalog_path.exists():
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            products = data.get("data", data) if isinstance(data, dict) else data
            for p in products:
                if p.get("id") == printify_id:
                    _log(f"[SYSTEM_LOG]: Local catalog metadata found for {printify_id}")
                    return p
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Failed to read local catalog: {e}")

    # 2. Check mockup product_link.json files
    mockup_dir = ROOT / "artifacts/graphics/mockups"
    for sub in mockup_dir.iterdir():
        if sub.is_dir() and printify_id in sub.name:
            link_file = sub / "product_link.json"
            if link_file.exists():
                try:
                    link = json.loads(link_file.read_text(encoding="utf-8"))
                    _log(f"[SYSTEM_LOG]: product_link.json found: {link_file}")
                    return link
                except Exception:
                    pass

    return None


def find_existing_lifestyle_image(printify_id: str) -> str | None:
    """Find the existing lifestyle mockup for this product ID."""
    mockup_dir = ROOT / "artifacts/graphics/mockups"
    for sub in mockup_dir.iterdir():
        if sub.is_dir() and printify_id in sub.name:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                for img in sub.iterdir():
                    if img.suffix.lower() == ext and img.name != "product_link.json":
                        return str(img)
    return None


# ── Model override prompt ────────────────────────────────────────────────────

def prompt_model_overrides(blueprint_meta: dict, product_title: str, printify_product: dict) -> dict:
    """
    Interactively prompt the Specialist for lifestyle model overrides.
    Presents detected defaults and allows per-category override.
    Returns an updated copy of blueprint_meta.
    """
    meta = dict(blueprint_meta)
    gender = meta.get("gender", "women")
    gender_label = {"women": "Female", "men": "Male", "nonbinary": "Non-binary"}.get(gender, "Female")

    print("\n" + "─" * 60)
    print("[MODEL_OVERRIDE]: Lifestyle model — press Enter to keep defaults")
    print("─" * 60)

    # ── GENDER ──
    print(f"  Gender       : {gender_label} (detected)")
    print("                 [F] Female  [M] Male  [N] Non-binary  [Enter] keep")
    choice = input("  → ").strip().lower()
    GENDER_MAP = {
        "f": ("women",    "a female model"),
        "m": ("men",      "a male model"),
        "n": ("nonbinary","a nonbinary model"),
    }
    if choice in GENDER_MAP:
        meta["gender"], meta["model"] = GENDER_MAP[choice]

    # ── ETHNICITY ──
    ETHNICITIES = [
        ("1", "not specified (let model decide)",   None),
        ("2", "Black / African",                     "a Black {g} model"),
        ("3", "Latina / Hispanic",                   "a Latina {g} model"),
        ("4", "South Asian",                         "a South Asian {g} model"),
        ("5", "East Asian",                          "an East Asian {g} model"),
        ("6", "Middle Eastern / North African",      "a Middle Eastern {g} model"),
        ("7", "Indigenous / Native",                 "an Indigenous {g} model"),
        ("8", "Mixed / multiracial",                 "a mixed-race {g} model"),
        ("9", "White / European",                    "a White {g} model"),
    ]
    print("\n  Ethnicity    : not specified (default)")
    for key, label, _ in ETHNICITIES:
        marker = " ← default" if key == "1" else ""
        print(f"    [{key}] {label}{marker}")
    choice = input("  → ").strip()
    gender_adj = {"women": "female", "men": "male", "nonbinary": "nonbinary"}.get(meta.get("gender", "women"), "female")
    for key, _, tmpl in ETHNICITIES:
        if choice == key:
            meta["ethnicity"] = tmpl.replace("{g}", gender_adj).strip() if tmpl else None
            break

    # ── BODY TYPE / SIZE FRAMING ──
    # Pull sizes from product options to frame naturally as garment size
    raw_sizes: list = []
    for opt in printify_product.get("options", []):
        if opt.get("type", "").lower() in ("size", "sizes"):
            for v in opt.get("values", []):
                t = v.get("title", "").strip()
                if t:
                    raw_sizes.append(t)

    SIZE_OPTS: list[tuple[str, str, str | None]] = [("1", "not specified (model decides)", None)]
    idx = 2
    for sz in raw_sizes:
        SIZE_OPTS.append((str(idx), f"wearing a {sz} (size framing)", sz))
        idx += 1
    SIZE_OPTS.append((str(idx), "plus-size / curvy build", "plus-size"))
    idx += 1
    SIZE_OPTS.append((str(idx), "athletic / muscular build", "athletic"))

    print("\n  Body type    : not specified (default)")
    for key, label, _ in SIZE_OPTS:
        marker = " ← default" if key == "1" else ""
        print(f"    [{key}] {label}{marker}")
    choice = input("  → ").strip()
    for key, _, val in SIZE_OPTS:
        if choice == key:
            meta["body_context"] = val  # None means omit
            break

    print("─" * 60)
    return meta


# ── Main verification flow ────────────────────────────────────────────────────

def verify_specimen(printify_id: str, dry_run: bool = False, batch: bool = False) -> bool:
    """
    Full verification ritual for a single UNVERIFIED SPECIMEN.
    Returns True on success, False on unrecoverable failure.
    """
    _log(f"[SYSTEM_LOG]: ═══ VERIFICATION RITUAL INITIATED ═══")
    _log(f"[SYSTEM_LOG]: Target Specimen: {printify_id}")

    shop_id = get_printify_shop_id() or get_shop_id()
    fab = Fabricator(shop_id=shop_id)
    conduit = ShopifyConduit()

    # ── 1. Fetch Printify product ─────────────────────────────────────────────
    _log("[SYSTEM_LOG]: Fetching Printify product data...")
    try:
        printify_product = get_printify_product(shop_id, printify_id)
    except Exception as e:
        _log(f"[SYSTEM_ERROR]: Cannot fetch Printify product {printify_id}: {e}")
        return False

    current_title = printify_product.get("title", "")
    description = printify_product.get("description", "").strip()

    if not current_title.upper().startswith("UNVERIFIED SPECIMEN"):
        _log(f"[SYSTEM_WARNING]: Product title does not start with 'UNVERIFIED SPECIMEN'.")
        _log(f"  Current title: {current_title!r}")
        answer = input("  This product may already be verified or have an unexpected title. Continue anyway? [y/N] ").strip().lower()
        if answer != "y":
            _log("[SYSTEM_LOG]: Verification aborted by operator.")
            return False

    # ── 2. Find Shopify product ───────────────────────────────────────────────
    _log("[SYSTEM_LOG]: Resolving Shopify product...")
    shopify_product = None
    shopify_id = None

    external = printify_product.get("external", {}) or {}
    ext_id = external.get("id")
    if ext_id:
        try:
            shopify_product = conduit.get_product(int(ext_id))
            shopify_id = int(ext_id)
            _log(f"[SYSTEM_LOG]: Shopify product found via external ID: {shopify_id}")
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Shopify fetch by external ID failed: {e}")

    if not shopify_product:
        _log("[SYSTEM_LOG]: Falling back to title-fragment search on Shopify...")
        shopify_product = find_shopify_product_by_title_fragment(conduit, printify_id)
        if shopify_product:
            shopify_id = shopify_product["id"]
            _log(f"[SYSTEM_LOG]: Shopify product found via title search: {shopify_id}")
        else:
            _log(f"[SYSTEM_ERROR]: Shopify product not found for {printify_id}.")
            _log("  The product may not have been published to Shopify yet.")
            answer = input("  Continue verification without Shopify sync? [y/N] ").strip().lower()
            if answer != "y":
                return False

    # ── 3. Determine product_type + blueprint meta (for gender-aware lifestyle) ─
    _log("[SYSTEM_LOG]: Resolving product_type...")
    product_type = None
    blueprint_meta: dict = {}

    if shopify_product:
        product_type = (shopify_product.get("product_type") or "").strip() or None

    # Always fetch blueprint meta for gender/model info (used later in lifestyle synthesis)
    blueprint_meta = fetch_blueprint_meta(printify_product)

    # Printify blueprint catalog titles often omit gender (e.g. "Full-Zip Hoodie" instead of
    # "Women's Full-Zip Hoodie"). Fall back to scanning the product title itself, then
    # garment type, then default to female.
    WOMENS_GARMENTS = {"leggings", "legging", "sports bra", "bra", "bikini", "skirt", "dress"}
    import re as _re
    raw_title = printify_product.get("title", "")
    tl = raw_title.lower()

    # Garment keywords or explicit "women" in title override blueprint gender (hard override).
    if any(g in tl for g in WOMENS_GARMENTS) or _re.search(r'\bwom[ae]n\b', tl):
        blueprint_meta = dict(blueprint_meta)
        blueprint_meta["gender"] = "women"
        blueprint_meta["model"] = "a female model"
    elif blueprint_meta.get("gender", "unisex") == "unisex":
        # Use word-boundary match to avoid false positives like "specimen" → "men"
        if _re.search(r"\bmen('s)?\b", tl) and not _re.search(r'\bwom[ae]n\b', tl):
            blueprint_meta = dict(blueprint_meta)
            blueprint_meta["gender"] = "men"
            blueprint_meta["model"] = "a male model"
        else:
            # Default: female model (safer for most CBG techwear products)
            blueprint_meta = dict(blueprint_meta)
            blueprint_meta["gender"] = "women"
            blueprint_meta["model"] = "a female model"

    if blueprint_meta.get("model"):
        _log(f"[SYSTEM_LOG]: Blueprint meta — gender: {blueprint_meta.get('gender')!r}, model: {blueprint_meta.get('model')!r}")

    # ── Prompt Specialist for model overrides (gender / ethnicity / body type) ─
    if not batch and not dry_run:
        blueprint_meta = prompt_model_overrides(blueprint_meta, raw_title, printify_product)
        _log(f"[SYSTEM_LOG]: Model overrides applied — gender: {blueprint_meta.get('gender')!r}, "
             f"ethnicity: {blueprint_meta.get('ethnicity')!r}, body: {blueprint_meta.get('body_context')!r}")

    if not product_type:
        product_type = blueprint_meta.get("product_type") or None
        if product_type:
            _log(f"[SYSTEM_LOG]: Inferred product_type from blueprint: {product_type!r}")
    if not product_type:
        _log("[SYSTEM_WARNING]: product_type missing from Shopify. Inferring from Printify blueprint...")
        product_type = infer_product_type_from_printify(printify_product)
        if product_type:
            _log(f"[SYSTEM_LOG]: Inferred product_type: {product_type!r}")
            if shopify_id and not dry_run:
                try:
                    conduit.update_product(shopify_id, {"product_type": product_type})
                    _log(f"[SYSTEM_LOG]: Shopify product_type updated to: {product_type!r}")
                except Exception as e:
                    _log(f"[SYSTEM_WARNING]: Failed to update Shopify product_type: {e}")
        else:
            _log("[SYSTEM_WARNING]: Could not infer product_type from blueprint.")
            product_type = input("  Enter product_type manually (e.g. 'Beach Shorts'): ").strip()
            if not product_type:
                _log("[SYSTEM_ERROR]: product_type is required. Aborting.")
                return False

    # ── 4. Resolve description prefix ────────────────────────────────────────
    _log("[SYSTEM_LOG]: Parsing description prefix...")

    # Prefer the live Printify description; fall back to Shopify body_html; then local catalog
    if not description and shopify_product:
        description = re.sub(r"<[^>]+>", "", shopify_product.get("body_html", "")).strip()

    if not description:
        _log("[SYSTEM_WARNING]: No description found on Printify or Shopify.")
        local_meta = find_local_product_metadata(printify_id)
        if local_meta:
            description = (local_meta.get("description") or "").strip()
            if description:
                _log(f"[SYSTEM_LOG]: Description recovered from local catalog: {description[:80]}...")

    prefix = None
    if description:
        prefix = parse_description_prefix(description)

    if not prefix:
        _log("[SYSTEM_WARNING]: Could not parse a prefix from the description.")
        _log(f"  Description: {description[:120]!r}")
        _log("  Expected format: 'CBG Studio | ... [theme]:...'")
        answer = input("  Enter the title prefix manually (e.g. 'CBG Studio | REMIX [A x B]'), or leave blank to abort: ").strip()
        if not answer:
            _log("[SYSTEM_ERROR]: No title prefix available. Aborting.")
            return False
        prefix = answer

    # ── 5. Build and validate new title ──────────────────────────────────────
    new_title = build_new_title(prefix, product_type, printify_id)
    _log(f"[SYSTEM_LOG]: New title: {new_title!r}")
    _log(f"[SYSTEM_LOG]: Title length: {len(new_title)} / {MAX_TITLE_LENGTH} chars")

    if len(new_title) > MAX_TITLE_LENGTH:
        _log(f"[SYSTEM_HALT]: Title exceeds {MAX_TITLE_LENGTH} characters ({len(new_title)}).")
        _log("  Please shorten the prefix or product_type before retrying.")
        _log(f"  PREFIX: {prefix!r}")
        _log(f"  PRODUCT_TYPE: {product_type!r}")
        return False

    if dry_run:
        _log("[DRY_RUN]: Would rename product to:")
        _log(f"  {new_title}")
        _log("[DRY_RUN]: Would set safety_information to EU GPSR compliance block (HONSON VENTURES).")
        _log("[DRY_RUN]: No changes written. Exiting.")
        return True

    # ── 6. Prepare the goose logo for upload ─────────────────────────────────
    _log("[SYSTEM_LOG]: Preparing green goose logo for Printify upload...")

    if not GOOSE_LOGO_PATH.exists():
        _log(f"[SYSTEM_ERROR]: Green goose logo not found at {GOOSE_LOGO_PATH}.")
        return False

    # Determine target size from the existing QR/logo images on this product
    logo_ids = _identify_logo_image_ids(printify_product)
    _log(f"[SYSTEM_LOG]: Logo-role image IDs in print_areas: {logo_ids or '(none)'}")

    if not logo_ids:
        _log("[SYSTEM_WARNING]: No logo-role images detected in print_areas.")
        _log("  The QR code may be applied only to the lifestyle image (not a Printify print area).")
        _log("  Skipping Printify print_areas logo replacement.")
        new_logo_id = None
        new_print_areas = None
    else:
        # Get size of first logo image to replicate dimensions
        logo_sizes = _get_logo_image_sizes(printify_product, logo_ids)
        ref_size = next(iter(logo_sizes.values()), (256, 256))
        _log(f"[SYSTEM_LOG]: QR code reference size: {ref_size[0]}×{ref_size[1]}px")

        # Resize goose to match and save to a temp file
        resized_goose = _resize_goose_to_match(GOOSE_LOGO_PATH, ref_size)
        tmp_goose_path = ROOT / "artifacts/graphics/logos/_goose_resized_tmp.png"
        resized_goose.save(str(tmp_goose_path))
        _log(f"[SYSTEM_LOG]: Goose resized to {ref_size[0]}×{ref_size[1]}px → {tmp_goose_path.name}")

        # Upload to Printify
        _log("[SYSTEM_LOG]: Uploading goose logo to Printify media library...")
        new_logo_id = upload_image_to_printify(fab, str(tmp_goose_path), f"green_goose_{printify_id}.png")
        try:
            tmp_goose_path.unlink()
        except Exception:
            pass

        if not new_logo_id:
            _log("[SYSTEM_ERROR]: Failed to upload goose logo to Printify. Aborting.")
            return False
        _log(f"[SYSTEM_LOG]: Goose logo uploaded. Printify image ID: {new_logo_id}")

        # Build new print_areas with goose swapped in
        new_print_areas = build_verified_print_areas(printify_product, logo_ids, new_logo_id)

    # ── 7. Update Printify product (title + print_areas + EU compliance) ──────
    _log("[SYSTEM_LOG]: Updating Printify product (title, EU safety info, logo swap)...")
    printify_update_payload = {
        "title": new_title,
        "safety_information": EU_SAFETY_INFORMATION,
    }
    if new_print_areas:
        printify_update_payload["print_areas"] = new_print_areas

    try:
        update_printify_product(shop_id, printify_id, printify_update_payload)
        _log(f"[SYSTEM_LOG]: Printify product updated: {new_title!r}")
    except Exception as e:
        _log(f"[SYSTEM_ERROR]: Failed to update Printify product: {e}")
        return False

    # ── 8. Publish (re-sync) updated product to Shopify ──────────────────────
    _log("[SYSTEM_LOG]: Triggering Printify → Shopify re-sync...")
    pub_url = f"{PRINTIFY_API_BASE}/shops/{shop_id}/products/{printify_id}/publish.json"
    pub_payload = {
        "title": True,
        "description": True,
        "images": True,
        "variants": True,
        "tags": True,
    }
    try:
        resp = requests.post(pub_url, headers=_printify_headers(), json=pub_payload)
        resp.raise_for_status()
        _log("[SYSTEM_LOG]: Publish triggered successfully.")
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Re-publish trigger failed: {e}. Continuing...")

    # Wait for sync to complete
    _log("[SYSTEM_LOG]: Waiting for Printify → Shopify sync...")
    try:
        synced_shopify_id = wait_for_printify_publish(shop_id, printify_id)
        if synced_shopify_id:
            shopify_id = int(synced_shopify_id)
            _log(f"[SYSTEM_LOG]: Sync complete. Shopify product ID: {shopify_id}")
    except Exception as e:
        _log(f"[SYSTEM_WARNING]: Sync wait failed: {e}. Proceeding with known Shopify ID.")
        if not shopify_id:
            _log("[SYSTEM_ERROR]: No Shopify product ID available. Cannot continue.")
            return False

    # ── 9. Synthesise new lifestyle image (goose-stamped) ────────────────────
    _log("[SYSTEM_LOG]: Synthesising verified lifestyle image...")

    # Re-fetch Printify product to get fresh mockup URLs
    try:
        fresh_product = get_printify_product(shop_id, printify_id)
        images = fresh_product.get("images", [])
    except Exception:
        images = printify_product.get("images", [])

    lifestyle_path = None
    mockup_url = None

    if images:
        mockup_url = images[0].get("src")
        for img in images:
            if "front" in img.get("src", "").lower():
                mockup_url = img.get("src")
                break

    if mockup_url:
        try:
            # Determine theme from description prefix for lifestyle prompt
            theme_context = prefix.replace("CBG Studio | ", "").rstrip()
            lifestyle_path = synthesize_lifestyle_mockup(
                theme=theme_context,
                product_title=new_title,
                mockup_url=mockup_url,
                blueprint_meta=blueprint_meta or None,
            )
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Lifestyle synthesis failed: {e}")
    else:
        _log("[SYSTEM_WARNING]: No mockup URL available for lifestyle synthesis.")

    import shutil

    old_lifestyle_path = find_existing_lifestyle_image(printify_id)

    if lifestyle_path:
        # Apply goose stamp (not QR)
        apply_goose_stamp(lifestyle_path)
        _log(f"[SYSTEM_LOG]: Goose-stamped lifestyle image: {lifestyle_path}")

        # Archive in a verified mockup folder.
        # Delete old file BEFORE copying so that if old and dest resolve to the
        # same path (re-run on already-verified product) we don't clobber ourselves.
        verified_folder = ROOT / "artifacts/graphics/mockups" / f"VERIFIED__{printify_id}"
        verified_folder.mkdir(parents=True, exist_ok=True)
        dest_path = verified_folder / Path(lifestyle_path).name

        if old_lifestyle_path and Path(old_lifestyle_path).resolve() != dest_path.resolve():
            if Path(old_lifestyle_path).exists():
                try:
                    Path(old_lifestyle_path).unlink()
                    _log(f"[SYSTEM_LOG]: Old lifestyle image removed: {old_lifestyle_path}")
                except Exception as e:
                    _log(f"[SYSTEM_WARNING]: Failed to remove old lifestyle image: {e}")

        shutil.copy2(lifestyle_path, str(dest_path))
        lifestyle_path = str(dest_path)
        _log(f"[SYSTEM_LOG]: Lifestyle archived → {verified_folder.name}/")
    else:
        # Synthesis failed — delete old QR-stamped image regardless.
        # A missing lifestyle image is preferable to one bearing the QR stamp.
        if old_lifestyle_path and Path(old_lifestyle_path).exists():
            try:
                Path(old_lifestyle_path).unlink()
                _log(f"[SYSTEM_LOG]: Old QR-stamped lifestyle image removed (synthesis failed, no fallback kept): {old_lifestyle_path}")
            except Exception as e:
                _log(f"[SYSTEM_WARNING]: Failed to remove old lifestyle image: {e}")
        _log("[SYSTEM_WARNING]: Lifestyle synthesis failed. No lifestyle image will be uploaded.")

    # ── 10. Upload lifestyle to Shopify ──────────────────────────────────────
    if shopify_id and lifestyle_path:
        _log(f"[SYSTEM_LOG]: Uploading verified lifestyle image to Shopify product {shopify_id}...")
        try:
            upload_lifestyle_image(shopify_id, lifestyle_path)
            _log(f"[SYSTEM_LOG]: Lifestyle image uploaded to Shopify.")
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Shopify lifestyle upload failed: {e}")
    elif not lifestyle_path:
        _log("[SYSTEM_WARNING]: No lifestyle image to upload. Skipping.")

    # ── 11. Update Shopify handle + create redirect ───────────────────────────
    if shopify_id:
        shopify_product = conduit.get_product(shopify_id)
        current_handle = shopify_product.get("handle", "")
        _log(f"[SYSTEM_LOG]: Current Shopify handle: {current_handle!r}")

        # Build new handle: remove "unverified-" prefix
        new_handle = re.sub(r"^unverified-", "", current_handle, flags=re.IGNORECASE)
        if new_handle == current_handle:
            # Broader fallback: replace 'unverified-specimen' with 'specimen' anywhere
            new_handle = re.sub(r"unverified-specimen", "specimen", current_handle, flags=re.IGNORECASE)

        if new_handle != current_handle:
            _log(f"[SYSTEM_LOG]: New Shopify handle: {new_handle!r}")
            try:
                conduit.update_product(shopify_id, {"handle": new_handle})
                _log(f"[SYSTEM_LOG]: Shopify handle updated.")
            except Exception as e:
                _log(f"[SYSTEM_WARNING]: Handle update failed: {e}")
                new_handle = current_handle  # keep old for redirect accuracy

            # Create redirect: old handle → new handle
            old_path = f"/products/{current_handle}"
            new_path = f"/products/{new_handle}"
            try:
                create_shopify_redirect(conduit, old_path, new_path)
            except Exception as e:
                _log(f"[SYSTEM_WARNING]: Redirect creation failed: {e}")
        else:
            _log(f"[SYSTEM_WARNING]: Handle does not contain 'unverified-'. No handle change needed.")

        # Update product_type on Shopify (reconfirm)
        try:
            conduit.update_product(shopify_id, {"product_type": product_type})
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: product_type re-confirm failed: {e}")

    # ── 12. Ensure Shopify smart collections exist for lore themes ────────────
    if shopify_id:
        try:
            ensure_lore_collections(conduit, new_title, dry_run=dry_run)
        except Exception as e:
            _log(f"[SYSTEM_WARNING]: Collection check/create failed: {e}")

    _log(f"[SYSTEM_SUCCESS]: ═══ SPECIMEN VERIFIED ═══")
    _log(f"  Printify ID  : {printify_id}")
    _log(f"  New title    : {new_title}")
    _log(f"  Shopify ID   : {shopify_id}")
    _log(f"  Handle       : {new_handle if shopify_id else '(unknown)'}")
    return True


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VERIFY SPECIMEN — transition an UNVERIFIED SPECIMEN to a branded product.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("printify_id", help="Printify product ID to verify.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the new title and detect issues without writing anything.",
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Skip interactive prompts and use auto-detected defaults for all model overrides.",
    )
    args = parser.parse_args()

    success = verify_specimen(args.printify_id, dry_run=args.dry_run, batch=args.batch)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
