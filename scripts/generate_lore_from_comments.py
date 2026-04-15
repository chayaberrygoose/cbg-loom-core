# /* [FILE_ID]: scripts/GENERATE_LORE_FROM_COMMENTS // VERSION: 3.0 // STATUS: STABLE */
# [NARRATIVE]: Extracts Specimen Lore from Shopify blog comments.
#              Each comment produces exactly ONE lore file — faithful 1:1 rendition.
#              Tracks processed comments and maintains a comment→lore mapping log.
#              Supports paginated comment fetching for any volume.
# [USAGE]: python scripts/generate_lore_from_comments.py
#          python scripts/generate_lore_from_comments.py --gemini
#          python scripts/generate_lore_from_comments.py --all

import os
import sys
import argparse
import re
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Ensure the project root is in the path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.skills.shopify_skill.shopify_skill import ShopifyConduit
from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data
from dotenv import load_dotenv

# Ollama support (default)
try:
    from agents.skills.ollama_skill.ollama_skill import (
        initialize_local_loom,
        generate_local_specimen_data,
        check_ollama_connection,
        RECOMMENDED_MODELS,
    )
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

load_dotenv()

# ─── DEFAULT LORE FEED POST ────────────────────────────────────
DEFAULT_BLOG_ID = 104538177748
DEFAULT_ARTICLE_ID = 593820188884

# ─── OUTPUT & TRACKING ─────────────────────────────────────────
LORE_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "lore"
LORE_TRACKER_FILE = LORE_OUTPUT_DIR / ".lore_comment_tracker.json"
LORE_MAPPING_FILE = LORE_OUTPUT_DIR / ".comment_lore_mapping.json"


# ─── TRACKING FUNCTIONS ────────────────────────────────────────

def load_tracker() -> Dict:
    """Load the v3 comment tracking data."""
    if not LORE_TRACKER_FILE.exists():
        return {"version": 3, "processed_ids": [], "last_run": None}
    try:
        with open(LORE_TRACKER_FILE, "r") as f:
            data = json.load(f)
        # Migration: if old v2 tracker, start fresh for v3 1:1 strategy
        if data.get("version") != 3:
            print("[SYSTEM_LOG]: Migrating tracker to v3 (1:1 comment→lore). Old tracker preserved.")
            return {"version": 3, "processed_ids": [], "last_run": None}
        return data
    except (json.JSONDecodeError, Exception):
        return {"version": 3, "processed_ids": [], "last_run": None}


def save_tracker(tracker: Dict) -> None:
    """Persist tracker to disk."""
    LORE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tracker["version"] = 3
    tracker["last_run"] = datetime.now().isoformat()
    with open(LORE_TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def get_unprocessed_comments(comments: List[Dict], tracker: Dict) -> List[Dict]:
    """Filter out comments already mapped to a lore file."""
    processed_ids = set(tracker.get("processed_ids", []))
    return [c for c in comments if c.get("id") not in processed_ids]


def mark_comment_processed(tracker: Dict, comment_id: int) -> None:
    """Mark a single comment as processed."""
    processed_ids = set(tracker.get("processed_ids", []))
    processed_ids.add(comment_id)
    tracker["processed_ids"] = list(processed_ids)


# ─── MAPPING LOG ───────────────────────────────────────────────

def load_mapping() -> Dict:
    """Load the comment→lore mapping log. Returns {comment_id_str: {lore_file, author, ...}}."""
    if LORE_MAPPING_FILE.exists():
        try:
            return json.loads(LORE_MAPPING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_mapping(mapping: Dict) -> None:
    """Persist the mapping log."""
    LORE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LORE_MAPPING_FILE.write_text(
        json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8"
    )


def record_mapping(comment: Dict, lore_filename: str) -> None:
    """Record a single comment→lore file association."""
    mapping = load_mapping()
    cid = str(comment.get("id"))
    mapping[cid] = {
        "lore_file": lore_filename,
        "author": comment.get("author", "Anonymous"),
        "comment_body": comment.get("body", "")[:200],
        "created_at": comment.get("created_at", ""),
        "mapped_at": datetime.now().isoformat(),
    }
    save_mapping(mapping)


# ─── PAGINATED COMMENT FETCHING ────────────────────────────────

def fetch_all_comments_paginated(
    conduit: ShopifyConduit,
    blog_id: int,
    article_id: int,
    status: str = "published",
) -> List[Dict]:
    """
    Fetch ALL comments for a blog article, following Shopify cursor-based
    pagination via the Link header. Works for any volume.
    """
    all_comments: List[Dict] = []
    page_size = 250
    params = {
        "limit": page_size,
        "status": status,
        "blog_id": blog_id,
        "article_id": article_id,
    }
    url = f"{conduit.base_url}/comments.json"

    page = 0
    while url:
        page += 1
        resp = requests.get(url, headers=conduit.headers, params=params if page == 1 else None)
        resp.raise_for_status()

        data = resp.json()
        comments = data.get("comments", [])
        all_comments.extend(comments)
        print(f"[SIGNAL_RECOVERY]: Page {page} — {len(comments)} comment(s) (total: {len(all_comments)})")

        # Follow Shopify cursor pagination via Link header
        link_header = resp.headers.get("Link", "")
        next_url = _parse_next_link(link_header)
        url = next_url  # None terminates the loop

        if not comments:
            break

    # Sort by ID ascending (oldest first) so lore files are created in chronological order
    all_comments.sort(key=lambda c: c.get("id", 0))
    return all_comments


def _parse_next_link(link_header: str) -> Optional[str]:
    """Extract the 'next' URL from a Shopify Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r'<([^>]+)>', part)
            if match:
                return match.group(1)
    return None


def generate_lore_prompt(comment_body: str, specimen_name: str) -> str:
    """
    Construct the prompt for lore synthesis from a SINGLE comment.
    Instructs the LLM to faithfully interpret the comment's content
    rather than averaging or generalizing.
    """
    return f"""You are generating a textile lore document for the Industrial Noir / Tech-Wear brand "Chaya Berry Goose" (CBG Studio).

A community member submitted this idea:

\"\"\"
{comment_body}
\"\"\"

Your task: Interpret this submission FAITHFULLY and render it as a structured lore file.
Do NOT generalize, average, or water down the idea. Capture the specific mood, imagery,
and aesthetic the commenter intended. If the comment is abstract, lean into the abstraction.
If it references specific materials, colors, or vibes, honor them precisely.

The specimen name is "{specimen_name}". Output ONLY in this exact Markdown format:

# {specimen_name}

## Description
(2-3 sentences. Technical, clinical language. Industrial noir aesthetic. Faithfully reflects the commenter's vision.)

## Palette
(4-6 colors as "Name (#HEXCODE)" entries, one per line with a leading dash. Derived from the comment's mood/imagery.)

## Motifs
(4-6 visual pattern keywords, comma-separated. Concrete and specific to THIS comment's theme.)

## Prompt Modifiers
(Comma-separated image generation keywords. Should capture the unique visual identity of this specific lore — not generic industrial noir.)

Rules:
- Section headers must be exactly: ## Description, ## Palette, ## Motifs, ## Prompt Modifiers
- No extra sections, no emojis, no code blocks
- Output the markdown document and nothing else
"""


def generate_specimen_name_for_comment(model, comment_body: str, generate_fn=None) -> str:
    """
    Generate a creative two-word Industrial Noir name that reflects
    the specific content of a single comment.
    """
    if generate_fn is None:
        generate_fn = generate_specimen_data

    # Use comment body directly (truncated for speed)
    snippet = comment_body[:500]

    prompt = f"""Generate ONE two-word name for an Industrial Noir textile pattern.

This name must reflect the specific mood and imagery of this community submission:
\"\"\"
{snippet}
\"\"\"

Rules:
- TWO words only, Title Case
- Dark/technical aesthetic (e.g., "Thermal Breach", "Void Circuit", "Signal Decay")
- The name should feel unique to THIS specific input, not generic
- Output ONLY the name, nothing else

Name:"""

    try:
        result = generate_fn(model, prompt)
        name = result.strip().split('\n')[0].strip()
        name = re.sub(r'["\']', '', name)
        name = re.sub(r'[.,!?:;]+$', '', name)
        words = name.split()
        if 1 <= len(words) <= 4:
            return name.title()
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Name generation failed — {e}")

    # Fallback
    import time
    return f"Specimen {int(time.time()) % 10000}"


def sanitize_filename(name: str) -> str:
    """Convert a specimen name to a valid filename."""
    sanitized = re.sub(r'[^\w\s\-]', '', name)
    return sanitized.strip()


def write_lore_file(specimen_name: str, content: str) -> Optional[Path]:
    """
    Write generated lore to a .md file.
    If the filename already exists, appends a numeric suffix.
    """
    LORE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = sanitize_filename(specimen_name)
    filepath = LORE_OUTPUT_DIR / f"{base}.md"

    # Avoid overwriting existing files from previous runs
    counter = 2
    while filepath.exists():
        filepath = LORE_OUTPUT_DIR / f"{base} {counter}.md"
        counter += 1

    try:
        filepath.write_text(content, encoding="utf-8")
        print(f"[SYSTEM_ECHO]: Lore written → {filepath}")
        return filepath
    except Exception as e:
        print(f"[SYSTEM_ERROR]: Failed to write lore file: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="[LORE_EXTRACTOR]: Generate one lore.md per Shopify blog comment (1:1 faithful rendition)."
    )
    parser.add_argument("--blog-id", type=int, help="Shopify blog ID")
    parser.add_argument("--article-id", type=int, help="Shopify article ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--max-comments", type=int, default=None,
                        help="Limit comments processed per run (default: all unprocessed)")
    parser.add_argument("--gemini", action="store_true", help="Use Gemini instead of Ollama")
    parser.add_argument("--model", type=str, help="Specify model name")
    parser.add_argument("--all", action="store_true",
                        help="Reprocess all comments (ignore tracker)")
    parser.add_argument("--status", action="store_true", help="Show tracker status and exit")
    parser.add_argument("--reset-tracking", action="store_true", help="Reset tracker to start fresh")

    args = parser.parse_args()

    # ── Tracking Status/Reset ───────────────────────────────────
    if args.status:
        tracker = load_tracker()
        mapping = load_mapping()
        print("[SYSTEM_LOG]: Lore Comment Tracker Status (v3)")
        print("-" * 40)
        print(f"  Last run:        {tracker.get('last_run', 'Never')}")
        print(f"  Processed count: {len(tracker.get('processed_ids', []))}")
        print(f"  Mapped lore:     {len(mapping)} file(s)")
        return

    if args.reset_tracking:
        save_tracker({"version": 3, "processed_ids": [], "last_run": None})
        print("[SYSTEM_LOG]: Tracker reset. All comments will be treated as new.")
        return

    # ── Initialize Shopify ──────────────────────────────────────
    print("[SYSTEM_INIT]: Establishing Shopify Uplink...")
    try:
        conduit = ShopifyConduit()
        conduit.check_connection()
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Failed to connect to Shopify — {e}")
        sys.exit(1)

    blog_id = args.blog_id or DEFAULT_BLOG_ID
    article_id = args.article_id or DEFAULT_ARTICLE_ID

    # ── Fetch ALL Comments (paginated) ──────────────────────────
    print(f"[SYSTEM_LOG]: Fetching all comments from blog {blog_id}, article {article_id}...")
    comments = fetch_all_comments_paginated(conduit, blog_id, article_id)

    if not comments:
        print("[SYSTEM_WARNING]: No comments retrieved. Nothing to generate.")
        sys.exit(1)

    print(f"[SYSTEM_LOG]: {len(comments)} total comment(s) retrieved.")

    # ── Filter to Unprocessed ───────────────────────────────────
    tracker = load_tracker()

    if args.all:
        print("[SYSTEM_LOG]: --all flag set. Processing every comment.")
        to_process = comments
    else:
        to_process = get_unprocessed_comments(comments, tracker)
        if not to_process:
            print("[SYSTEM_LOG]: No new comments to process. Use --all to reprocess.")
            return
        print(f"[SYSTEM_LOG]: {len(to_process)} unprocessed comment(s).")

    if args.max_comments and len(to_process) > args.max_comments:
        to_process = to_process[:args.max_comments]
        print(f"[SYSTEM_LOG]: Capped at {args.max_comments} comment(s) this run.")

    # ── Initialize LLM Backend ──────────────────────────────────
    model, generate_fn, backend = _init_llm_backend(args)

    # ── Process Each Comment → 1 Lore File ──────────────────────
    generated = []
    failed = 0

    for idx, comment in enumerate(to_process, 1):
        cid = comment.get("id")
        author = comment.get("author", "Anonymous")
        body = comment.get("body", "").strip()

        if not body:
            print(f"[SYSTEM_WARNING]: Comment {cid} has empty body. Skipping.")
            mark_comment_processed(tracker, cid)
            continue

        print(f"\n[SYSTEM_LOG]: ─── Comment {idx}/{len(to_process)} (ID: {cid}, Author: {author}) ───")
        print(f"  Body: {body[:120]}{'...' if len(body) > 120 else ''}")

        # 1. Generate specimen name from this specific comment
        print(f"[SYSTEM_LOG]: Generating specimen name via {backend}...")
        specimen_name = generate_specimen_name_for_comment(model, body, generate_fn)
        print(f"[SYSTEM_LOG]: Specimen Name → {specimen_name}")

        # 2. Generate lore content faithful to this comment
        prompt = generate_lore_prompt(body, specimen_name)
        print(f"[SYSTEM_LOG]: Synthesizing lore via {backend}...")
        lore_content = generate_fn(model, prompt)

        if lore_content.startswith("[SYSTEM_FAILURE]") or lore_content.startswith("[ACCESS_DENIED]"):
            print(f"[SYSTEM_WARNING]: LLM failed for comment {cid}: {lore_content[:100]}")
            failed += 1
            continue

        # 3. Write or preview
        if args.dry_run:
            print("\n" + "=" * 60)
            print(f"[DRY_RUN]: {specimen_name} (from comment {cid})")
            print("=" * 60)
            print(lore_content)
            print("=" * 60)
        else:
            filepath = write_lore_file(specimen_name, lore_content)
            if filepath:
                generated.append((specimen_name, filepath, cid))
                record_mapping(comment, filepath.name)

        # 4. Mark processed
        mark_comment_processed(tracker, cid)

    # ── Persist Tracker ─────────────────────────────────────────
    if not args.dry_run:
        save_tracker(tracker)

    # ── Summary ─────────────────────────────────────────────────
    print(f"\n[SYSTEM_SUCCESS]: Lore extraction complete.")
    print(f"  Generated: {len(generated)} file(s)")
    print(f"  Failed:    {failed}")
    if generated:
        for name, path, cid in generated:
            print(f"    • {name}: {path.name} (comment {cid})")


def _init_llm_backend(args) -> Tuple:
    """
    Initialize the LLM backend (Ollama or Gemini). Returns (model, generate_fn, backend_name).
    """
    use_gemini = args.gemini
    model = None

    if use_gemini:
        print("[SYSTEM_INIT]: Establishing Gemini Loom Uplink...")
        model = initialize_loom_uplink(args.model)
        if model:
            return model, generate_specimen_data, "Gemini"
        # Gemini failed — try Ollama fallback
        if OLLAMA_AVAILABLE and check_ollama_connection():
            print("[SYSTEM_LOG]: Gemini unavailable. Falling back to Ollama...")
            model = initialize_local_loom(args.model)
            if model:
                return model, generate_local_specimen_data, "Ollama"
        print("[SYSTEM_DISSONANCE]: No inference backend available.")
        sys.exit(1)

    # Default: Ollama
    if not OLLAMA_AVAILABLE:
        print("[SYSTEM_WARNING]: Ollama skill not installed. Trying Gemini...")
        model = initialize_loom_uplink(args.model)
        if model:
            return model, generate_specimen_data, "Gemini"
        print("[SYSTEM_DISSONANCE]: No inference backend available.")
        sys.exit(1)

    if not check_ollama_connection():
        print("[SYSTEM_WARNING]: Ollama not running. Trying Gemini...")
        model = initialize_loom_uplink(args.model)
        if model:
            return model, generate_specimen_data, "Gemini"
        print("[SYSTEM_DISSONANCE]: Ollama not running and Gemini not configured.")
        print("[SYSTEM_HINT]: Start Ollama with: ollama serve")
        sys.exit(1)

    print("[SYSTEM_INIT]: Establishing Local Loom Uplink (Ollama)...")
    model = initialize_local_loom(args.model)
    if not model:
        print("[SYSTEM_DISSONANCE]: No Ollama models available.")
        print(f"[SYSTEM_HINT]: Pull a model with: ollama pull {RECOMMENDED_MODELS[0]}")
        sys.exit(1)
    return model, generate_local_specimen_data, "Ollama"


if __name__ == "__main__":
    main()
