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

# ── Image selection ────────────────────────────────────────────────────────────
def select_mockup_image(product: dict) -> tuple[str, str]:
    """
    Pick the best flat mockup image URL from a Printify product.

    Printify's `images` array contains its own rendered mockups (apparel on
    white / neutral backgrounds).  We prefer:
      1. The default image (is_default=True).
      2. Front-position images.
      3. Anything else in the array.

    Returns (url, position_label).
    """
    images = product.get("images", [])
    if not images:
        raise ValueError("[SIGNAL_LOSS]: No images found on this product.")

    # Priority 1 — default image
    for img in images:
        if img.get("is_default"):
            return img["src"], img.get("position", "default")

    # Priority 2 — front position
    for img in images:
        if str(img.get("position", "")).lower() == "front":
            return img["src"], "front"

    # Fallback — first image
    first = images[0]
    return first["src"], first.get("position", "unknown")

def fetch_image_bytes(url: str) -> bytes:
    """Download an image from a URL and return raw bytes."""
    resp = _requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content

# ── Prompt assembly ────────────────────────────────────────────────────────────
_BASE_ATMOSPHERE = (
    "A cinematic, high-fidelity product advertisement for an Industrial Noir × Tech-Wear garment. "
    "The garment is the central, anchoring subject throughout. "
    "Atmosphere and environment have full creative latitude: "
    "dramatic industrial lighting, moody noir backdrops, neon accents, "
    "or sub-atomic particle fields are all welcome. "
    "The visual narrative should feel raw, sovereign, and high-signal. "
    "Use a sequence of composed camera movements: "
    "open with a slow full-body reveal of the garment against an atmospheric background, "
    "then transition to deliberate close-up shots isolating the all-over print pattern — "
    "texture, linework, and colour detail — treating the print like a landscape. "
    "Cut back to a mid-distance tracking shot to close. "
    "All camera movements must be slow and stable; no rapid cuts or shaky motion. "
    "The print artwork on the garment must remain sharp and undistorted in every frame."
)

# Topology lock removed — mentioning the logo in the prompt causes Veo to
# zoom into it and hallucinate structure beyond the image resolution.
# Print fidelity is enforced via _TOPOLOGY_LOCK without naming the goose,
# and camera direction explicitly keeps wide/mid/pattern framing only.
_TOPOLOGY_LOCK = (
    "All graphic elements and print artwork on the garment must remain "
    "pixel-faithful and undistorted throughout — treat every printed motif "
    "as a static texture map that does not morph, blur, or animate independently. "
    "Do not zoom into any logo or emblem; camera framing must stay at "
    "full-body, mid-distance, or close-up on the all-over print pattern only."
)

_STABILITY_MODIFIER = (
    "Slow, stable tracking shot. No rapid camera movements. "
    "Maintain a locked focus on the central subject."
)

def build_prompt(product: dict, goose: bool) -> str:
    product_title = product.get("title", "CBG Studio product")
    # Strip the canonical prefix for a cleaner description
    clean_title = re.sub(r"^CBG Studio \| ", "", product_title, flags=re.IGNORECASE)
    clean_title = re.sub(r"\| SPECIMEN:.*$", "", clean_title).strip()

    parts = [
        f"Product: {clean_title}.",
        _BASE_ATMOSPHERE,
    ]

    if goose:
        parts.append(_TOPOLOGY_LOCK)

    return " ".join(parts)

# ── Veo generation ─────────────────────────────────────────────────────────────
def generate_video(
    *,
    model: str,
    prompt: str,
    image_bytes: bytes,
    mime_type: str,
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

    operation = client.models.generate_videos(
        model=model,
        prompt=prompt,
        image=gtypes.Image(image_bytes=image_bytes, mime_type=mime_type),
        config=gtypes.GenerateVideosConfig(
            aspect_ratio=ASPECT_RATIO,
            number_of_videos=1,
            duration_seconds=duration,
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

    # ── Select image ───────────────────────────────────────────────────────────
    img_url, img_position = select_mockup_image(product)
    print(f"[SYSTEM_LOG]: Selected image (position={img_position}) → {img_url[:80]}…")

    # Infer MIME type from URL
    mime_type = "image/jpeg" if img_url.lower().endswith((".jpg", ".jpeg")) else "image/png"

    # ── Goose detection ────────────────────────────────────────────────────────
    goose = has_goose_logo(product)
    if goose:
        print("[SYSTEM_LOG]: Goose logo detected — topology lock modifier ACTIVE.")
    else:
        print("[SYSTEM_LOG]: QR-stamp variant (unverified) — topology lock modifier SKIPPED.")

    # ── Build prompt ───────────────────────────────────────────────────────────
    prompt = build_prompt(product, goose)

    # ── Resolve output path ────────────────────────────────────────────────────
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", args.product_id)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = args.out_dir / f"{safe_id}_{ts}.mp4"

    # ── Fetch image bytes (skip in dry-run to avoid latency) ───────────────────
    if not args.dry_run:
        print(f"[SYSTEM_LOG]: Downloading reference image …")
        try:
            image_bytes = fetch_image_bytes(img_url)
        except Exception as exc:
            print(f"[SIGNAL_LOSS]: Could not download image — {exc}")
            sys.exit(1)
    else:
        image_bytes = b""  # not needed for dry-run display

    # ── Generate ───────────────────────────────────────────────────────────────
    generate_video(
        model=args.model,
        prompt=prompt,
        image_bytes=image_bytes,
        mime_type=mime_type,
        duration=args.duration,
        dry_run=args.dry_run,
        out_path=out_path,
    )


if __name__ == "__main__":
    main()
