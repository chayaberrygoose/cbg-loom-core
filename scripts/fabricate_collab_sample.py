#!/usr/bin/env python3
"""
Generic collab prototype scaffold

Purpose: isolated, non-invasive sample pipeline for prototype collaborations.
- Default: dry-run only (no external publish).
- Optional: `--publish` only works if you explicitly set env vars and confirm.

This file is intentionally generic so it can be reused for future collaborations.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from pathlib import Path
from datetime import datetime

ARTIFACTS_DIR = Path("artifacts/collab")


def ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


def sanitize_name(name: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    name = name.lower().replace(" ", "-")
    return "".join(ch for ch in name if ch in keep)


def copy_image_to_artifacts(src: Path, prefix: str) -> Path:
    ensure_artifacts_dir()
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dst_name = f"{prefix}-{ts}{src.suffix}"
    dst = ARTIFACTS_DIR / dst_name
    shutil.copy2(src, dst)
    return dst


def prepare_draft_payload(image_paths: list[Path], product_name: str, template_id: str | None) -> dict:
    payload = {
        "product_name": product_name,
        "template_id": template_id,
        "images": [str(p) for p in image_paths],
        "meta": {"created_at": datetime.utcnow().isoformat() + "Z"},
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic collab prototype scaffold (dry-run by default)")
    parser.add_argument("--images", nargs="+", help="Path(s) to image files to include", required=True)
    parser.add_argument("--product-name", default="collab-sample", help="Draft product name")
    parser.add_argument("--template-id", default=None, help="Optional template id to map against")
    parser.add_argument("--publish", action="store_true", help="Only enable publishing when set and env vars are configured")
    parser.add_argument("--confirm-publish", action="store_true", help="Double-confirm publish (extra safety)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    src_paths = [Path(p) for p in args.images]
    for p in src_paths:
        if not p.exists():
            logging.error("Image not found: %s", p)
            return 2

    # Copy images into artifacts for traceability
    copied = []
    prefix = sanitize_name(args.product_name)
    for p in src_paths:
        dst = copy_image_to_artifacts(p, prefix)
        logging.info("Copied %s -> %s", p, dst)
        copied.append(dst)

    payload = prepare_draft_payload(copied, args.product_name, args.template_id)

    # Always print the draft payload and write a local JSON for review
    out = ARTIFACTS_DIR / (prefix + "-draft-payload.json")
    out.write_text(json.dumps(payload, indent=2))
    logging.info("Draft payload written to %s", out)
    logging.info("Dry-run: not publishing to external services by default.")

    # Safety: publishing only if user opts in and confirms and required env vars are present
    if args.publish:
        required = ["PRINTIFY_API_KEY", "PRINTIFY_SHOP_ID"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            logging.error("Cannot publish: missing env vars: %s", ",".join(missing))
            logging.info("Payload saved; use --publish with env vars and --confirm-publish to actually publish.")
            return 3
        if not args.confirm_publish:
            logging.error("Publish blocked: must pass --confirm-publish to proceed.")
            return 4

        # At this point, a real publishing flow could be invoked. We keep this generic and explicit.
        logging.info("Publish requested and confirmed. Implement the publish hooks where indicated in this file.")
        # TODO: integrate with project fabricator client if desired.

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
