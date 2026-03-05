# /* [FILE_ID]: scripts/GENERATE_LORE_FROM_COMMENTS // VERSION: 2.0 // STATUS: STABLE */
# [NARRATIVE]: Extracts Specimen Lore from Shopify blog comments,
#              synthesizes structured lore.md files via local Ollama (default) or Gemini.
#              Tracks processed comments to avoid re-processing.
# [USAGE]: python scripts/generate_lore_from_comments.py
#          python scripts/generate_lore_from_comments.py --gemini
#          python scripts/generate_lore_from_comments.py --all  # Process all, ignore tracking

import os
import sys
import argparse
import re
import json
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
# Hardcoded until further notice
DEFAULT_BLOG_ID = 104538177748
DEFAULT_ARTICLE_ID = 593820188884

# ─── OUTPUT & TRACKING DIRECTORIES ─────────────────────────────
LORE_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "lore"
LORE_TRACKER_FILE = LORE_OUTPUT_DIR / ".lore_comment_tracker.json"

# ─── BATCH SETTINGS ────────────────────────────────────────────
# Minimum comments needed to generate a lore file
MIN_COMMENTS_PER_LORE = 3
# Maximum comments to use per lore file  
MAX_COMMENTS_PER_LORE = 8


# ─── TRACKING FUNCTIONS ────────────────────────────────────────
def load_tracker() -> Dict:
    """Load the comment tracking data."""
    if not LORE_TRACKER_FILE.exists():
        return {"last_comment_id": None, "processed_ids": [], "last_run": None}
    try:
        with open(LORE_TRACKER_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {"last_comment_id": None, "processed_ids": [], "last_run": None}


def save_tracker(tracker: Dict) -> None:
    """Save the comment tracking data."""
    LORE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tracker["last_run"] = datetime.now().isoformat()
    with open(LORE_TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def get_unprocessed_comments(comments: List[Dict], tracker: Dict) -> List[Dict]:
    """Filter out comments that have already been processed."""
    processed_ids = set(tracker.get("processed_ids", []))
    return [c for c in comments if c.get("id") not in processed_ids]


def mark_comments_processed(tracker: Dict, comments: List[Dict]) -> Dict:
    """Mark comments as processed in the tracker."""
    processed_ids = set(tracker.get("processed_ids", []))
    for c in comments:
        processed_ids.add(c.get("id"))
    tracker["processed_ids"] = list(processed_ids)
    if comments:
        # Track the highest comment ID
        max_id = max(c.get("id", 0) for c in comments)
        if not tracker.get("last_comment_id") or max_id > tracker["last_comment_id"]:
            tracker["last_comment_id"] = max_id
    return tracker


def fetch_comments(
    conduit: ShopifyConduit,
    blog_id: Optional[int] = None,
    article_id: Optional[int] = None,
    status: str = "published",
) -> List[Dict]:
    """
    Retrieve comments from the Shopify Archive.
    """
    print(f"[SIGNAL_RECOVERY]: Fetching comments (blog_id={blog_id}, article_id={article_id})...")
    comments = conduit.list_comments(
        blog_id=blog_id,
        article_id=article_id,
        status=status,
        limit=250,
    )
    return comments


def extract_lore_seeds(comments: List[Dict]) -> str:
    """
    Compile comment data into a seed text for Gemini synthesis.
    Extracts author names, body text, and any relevant metadata.
    """
    if not comments:
        return ""

    seeds = []
    for c in comments:
        author = c.get("author", "Anonymous")
        body = c.get("body", "").strip()
        email = c.get("email", "")
        created_at = c.get("created_at", "")

        if body:
            seeds.append(f"[{author}]: {body}")

    return "\n".join(seeds)


def generate_lore_prompt(seed_text: str, specimen_name: str) -> str:
    """
    Construct the Gemini prompt for lore synthesis.
    """
    return f"""You are a Digital Architect for "Chaya Berry Goose" (CBG Studio), an Industrial Noir / Tech-Wear brand.
Your task is to generate a textile lore document for a new design pattern called "{specimen_name}".

Use the following community input as inspiration:
---
{seed_text}
---

Generate a lore document in this exact Markdown format:

# {specimen_name}

## Description
(Write 2-3 sentences describing the visual aesthetic and concept. Use technical, clinical language with industrial noir undertones.)

## Palette
(List 4-6 colors as comma-separated values, including hex codes where appropriate. Examples: "Neon green (#39FF14), deep violet, surgical steel, void black")

## Motifs
(List 4-6 visual motifs/patterns as comma-separated values. Examples: "Motion blur streaks, digital progress bars, pixel-fall, fiber-optic bundles")

## Prompt Modifiers
(Write 1-2 sentences of comma-separated prompt modifiers for MidJourney/Stable Diffusion image generation. Keep technical and specific.)

IMPORTANT:
- Keep the tone clinical, high-fidelity, and technical.
- Reference concepts like: circuitry, data streams, glitches, industrial textures, technical fabrics.
- Do NOT include emojis or casual language.
- The output should be usable directly as a .md file.
"""


def sanitize_filename(name: str) -> str:
    """Convert a specimen name to a valid filename."""
    # Replace spaces with spaces (keep them), remove special chars
    sanitized = re.sub(r'[^\w\s\-]', '', name)
    return sanitized.strip()


def generate_specimen_name(model, seed_text: str, generate_fn=None) -> str:
    """
    Use LLM (Gemini or Ollama) to generate a creative Industrial Noir specimen name.
    Returns a two-word name in Title Case.
    """
    if generate_fn is None:
        generate_fn = generate_specimen_data
        
    prompt = """You are naming a new textile pattern for "Chaya Berry Goose", an Industrial Noir / Tech-Wear brand.

Based on the following community input, generate ONE unique two-word specimen name.
The name should evoke industrial, technical, or scientific concepts.

Community input:
---
""" + seed_text[:1500] + """
---

Rules:
- Exactly TWO words, Title Case (e.g., "Thermal Breach", "Obsidian Circuit", "Phantom Grid")
- Industrial Noir aesthetic: dark, technical, clinical
- Reference concepts like: circuitry, data, signals, voids, glitches, machinery, textiles
- NO emojis, NO punctuation, NO explanations
- Just output the two-word name, nothing else

Examples of good names: Neon Siphon, Void Mantle, Signal Flare, Kinetic Residue, Cryptic Weave

Your specimen name:"""

    try:
        result = generate_fn(model, prompt)
        # Clean up the result - extract just the name
        name = result.strip().split('\n')[0].strip()
        # Remove any quotes or extra punctuation
        name = re.sub(r'["\']', '', name)
        # Validate it's roughly two words
        words = name.split()
        if 1 <= len(words) <= 4:
            return name.title()
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Name generation failed — {e}")

    # Fallback to timestamp-based name
    import time
    return f"Specimen {int(time.time()) % 10000}"


def derive_specimen_name(comments: List[Dict], article_title: Optional[str] = None) -> str:
    """
    DEPRECATED: Use generate_specimen_name() instead.
    Derive a specimen name from comments or article metadata.
    Falls back to a generated name if no clear pattern emerges.
    """
    if article_title:
        # Clean up the article title for use as a specimen name
        name = re.sub(r'[^\w\s\-]', '', article_title).strip()
        if name:
            return name

    # Fallback: generate from comment content keywords
    all_text = " ".join([c.get("body", "") for c in comments])
    words = all_text.split()[:3]
    if words:
        return " ".join(words).title()

    return "Unknown Specimen"


def write_lore_file(specimen_name: str, content: str) -> Path:
    """
    Write the generated lore to a .md file.
    """
    LORE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{sanitize_filename(specimen_name)}.md"
    filepath = LORE_OUTPUT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[SYSTEM_ECHO]: Lore written → {filepath}")
    return filepath


def interactive_article_selection(conduit: ShopifyConduit) -> tuple:
    """
    Interactive mode: list blogs and articles, let user select.
    Returns (blog_id, article_id, article_title).
    """
    print("\n[SYSTEM_SCAN]: Available Blogs")
    print("-" * 40)
    blogs = conduit.list_blogs()

    if not blogs:
        print("[SYSTEM_DISSONANCE]: No blogs found.")
        return None, None, None

    blog_id = int(input("\nEnter blog ID: ").strip())

    print(f"\n[SYSTEM_SCAN]: Articles in Blog {blog_id}")
    print("-" * 40)
    articles = conduit.list_articles(blog_id, limit=50)

    if not articles:
        print("[SYSTEM_DISSONANCE]: No articles found in this blog.")
        return blog_id, None, None

    article_id = int(input("\nEnter article ID: ").strip())

    # Find article title
    article_title = None
    for a in articles:
        if a.get("id") == article_id:
            article_title = a.get("title")
            break

    return blog_id, article_id, article_title


def main():
    parser = argparse.ArgumentParser(
        description="[LORE_EXTRACTOR]: Generate lore.md files from Shopify blog comments."
    )
    parser.add_argument(
        "--blog-id",
        type=int,
        help="Shopify blog ID",
    )
    parser.add_argument(
        "--article-id",
        type=int,
        help="Shopify article ID",
    )
    parser.add_argument(
        "--specimen-name",
        type=str,
        help="Override the specimen name (default: derived from article title)",
    )
    parser.add_argument(
        "--list-blogs",
        action="store_true",
        help="List available blogs and exit",
    )
    parser.add_argument(
        "--list-articles",
        type=int,
        metavar="BLOG_ID",
        help="List articles for a blog and exit",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode: browse blogs/articles",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show generated lore without writing to file",
    )
    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Use Gemini API instead of local Ollama (Ollama is default)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specify model name (for Ollama: llama3.2:3b, gemma2:2b, etc.)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all comments, ignoring tracking (reprocess everything)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show tracking status and exit",
    )
    parser.add_argument(
        "--reset-tracking",
        action="store_true",
        help="Reset the comment tracker (start fresh)",
    )

    args = parser.parse_args()

    # ── Tracking Status/Reset ───────────────────────────────────
    if args.status:
        tracker = load_tracker()
        print("[SYSTEM_LOG]: Lore Comment Tracker Status")
        print("-" * 40)
        print(f"  Last run:        {tracker.get('last_run', 'Never')}")
        print(f"  Last comment ID: {tracker.get('last_comment_id', 'None')}")
        print(f"  Processed count: {len(tracker.get('processed_ids', []))}")
        return

    if args.reset_tracking:
        save_tracker({"last_comment_id": None, "processed_ids": [], "last_run": None})
        print("[SYSTEM_LOG]: Tracker reset. All comments will be treated as new.")
        return

    # ── Initialize Shopify Conduit ──────────────────────────────
    print("[SYSTEM_INIT]: Establishing Shopify Uplink...")
    try:
        conduit = ShopifyConduit()
        conduit.check_connection()
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Failed to connect to Shopify — {e}")
        sys.exit(1)

    # ── List Mode ───────────────────────────────────────────────
    if args.list_blogs:
        conduit.list_blogs()
        return

    if args.list_articles:
        conduit.list_articles(args.list_articles)
        return

    # ── Interactive Mode ────────────────────────────────────────
    if args.interactive:
        blog_id, article_id, article_title = interactive_article_selection(conduit)
        if not article_id:
            print("[SYSTEM_ABORT]: No article selected.")
            sys.exit(1)
    else:
        # Default to Lore Feed post if no IDs provided
        blog_id = args.blog_id or DEFAULT_BLOG_ID
        article_id = args.article_id or DEFAULT_ARTICLE_ID
        article_title = None

        if blog_id == DEFAULT_BLOG_ID and article_id == DEFAULT_ARTICLE_ID:
            print(f"[SYSTEM_LOG]: Using default Lore Feed post ({DEFAULT_BLOG_ID}/{DEFAULT_ARTICLE_ID})")

        if article_id and blog_id:
            # Fetch article title
            article = conduit.get_article(blog_id, article_id)
            article_title = article.get("title")

    # ── Fetch Comments ──────────────────────────────────────────
    comments = fetch_comments(conduit, blog_id=blog_id, article_id=article_id)

    if not comments:
        print("[SYSTEM_WARNING]: No comments retrieved. Cannot generate lore.")
        sys.exit(1)

    print(f"[SYSTEM_LOG]: Retrieved {len(comments)} total comment(s).")

    # ── Filter Unprocessed Comments ─────────────────────────────
    tracker = load_tracker()
    
    if args.all:
        print("[SYSTEM_LOG]: --all flag set, processing all comments.")
        unprocessed = comments
    else:
        unprocessed = get_unprocessed_comments(comments, tracker)
        if not unprocessed:
            print("[SYSTEM_LOG]: No new comments to process. Use --all to reprocess.")
            return
        print(f"[SYSTEM_LOG]: {len(unprocessed)} new comment(s) to process.")

    # ── Initialize Model (Ollama default) ───────────────────────
    use_gemini = args.gemini
    model = None
    generate_fn = None
    
    if use_gemini:
        print("[SYSTEM_INIT]: Establishing Gemini Loom Uplink...")
        model = initialize_loom_uplink(args.model)
        if not model:
            print("[SYSTEM_DISSONANCE]: Failed to initialize Gemini. Check GOOGLE_API_KEY.")
            # Try Ollama fallback
            if OLLAMA_AVAILABLE and check_ollama_connection():
                print("[SYSTEM_LOG]: Falling back to Ollama...")
                model = initialize_local_loom(args.model)
                if model:
                    use_gemini = False
                    generate_fn = generate_local_specimen_data
            if not model:
                sys.exit(1)
        else:
            generate_fn = generate_specimen_data
    else:
        # Default: Use Ollama
        if not OLLAMA_AVAILABLE:
            print("[SYSTEM_WARNING]: Ollama skill not installed. Trying Gemini...")
            model = initialize_loom_uplink(args.model)
            if model:
                use_gemini = True
                generate_fn = generate_specimen_data
            else:
                print("[SYSTEM_DISSONANCE]: No inference backend available.")
                sys.exit(1)
        elif not check_ollama_connection():
            print("[SYSTEM_WARNING]: Ollama not running. Trying Gemini...")
            model = initialize_loom_uplink(args.model)
            if model:
                use_gemini = True
                generate_fn = generate_specimen_data
            else:
                print("[SYSTEM_DISSONANCE]: Ollama not running and Gemini not configured.")
                print("[SYSTEM_HINT]: Start Ollama with: ollama serve")
                sys.exit(1)
        else:
            print("[SYSTEM_INIT]: Establishing Local Loom Uplink (Ollama)...")
            model = initialize_local_loom(args.model)
            if not model:
                print("[SYSTEM_DISSONANCE]: No Ollama models available.")
                print(f"[SYSTEM_HINT]: Pull a model with: ollama pull {RECOMMENDED_MODELS[0]}")
                sys.exit(1)
            generate_fn = generate_local_specimen_data

    backend = "Gemini" if use_gemini else "Ollama"

    # ── Batch Process Comments into Lore Files ──────────────────
    # Group comments into batches for lore generation
    batches = []
    current_batch = []
    
    for comment in unprocessed:
        current_batch.append(comment)
        if len(current_batch) >= MAX_COMMENTS_PER_LORE:
            batches.append(current_batch)
            current_batch = []
    
    # Handle remaining comments
    if current_batch:
        if len(current_batch) >= MIN_COMMENTS_PER_LORE:
            batches.append(current_batch)
        elif batches:
            # Add to last batch if exists
            batches[-1].extend(current_batch)
        else:
            # Not enough comments for a lore file
            print(f"[SYSTEM_WARNING]: Only {len(current_batch)} comment(s). Need at least {MIN_COMMENTS_PER_LORE}.")
            print("[SYSTEM_HINT]: Wait for more comments or use --all with existing comments.")
            return

    print(f"[SYSTEM_LOG]: Will generate {len(batches)} lore file(s).")

    generated_files = []
    processed_comments = []

    for batch_idx, batch in enumerate(batches, 1):
        print(f"\n[SYSTEM_LOG]: Processing batch {batch_idx}/{len(batches)} ({len(batch)} comments)...")
        
        # Extract seeds from this batch
        seed_text = extract_lore_seeds(batch)
        
        # Generate specimen name
        if args.specimen_name and len(batches) == 1:
            specimen_name = args.specimen_name
        else:
            print(f"[SYSTEM_LOG]: Generating specimen name via {backend}...")
            specimen_name = generate_specimen_name(model, seed_text, generate_fn)
        print(f"[SYSTEM_LOG]: Specimen Name → {specimen_name}")

        # Generate lore content
        prompt = generate_lore_prompt(seed_text, specimen_name)
        print(f"[SYSTEM_LOG]: Synthesizing lore via {backend}...")
        
        lore_content = generate_fn(model, prompt)

        if lore_content.startswith("[SYSTEM_FAILURE]") or lore_content.startswith("[ACCESS_DENIED]"):
            print(f"[SYSTEM_WARNING]: Batch {batch_idx} failed — {lore_content}")
            continue

        # Output
        if args.dry_run:
            print("\n" + "=" * 60)
            print(f"[DRY_RUN]: Lore Preview (Batch {batch_idx})")
            print("=" * 60)
            print(lore_content)
            print("=" * 60)
        else:
            filepath = write_lore_file(specimen_name, lore_content)
            generated_files.append((specimen_name, filepath))

        # Track these comments as processed
        processed_comments.extend(batch)

    # ── Update Tracker ──────────────────────────────────────────
    if not args.dry_run and processed_comments:
        tracker = mark_comments_processed(tracker, processed_comments)
        save_tracker(tracker)
        print(f"\n[SYSTEM_LOG]: Tracker updated. {len(processed_comments)} comments marked processed.")

    # ── Summary ─────────────────────────────────────────────────
    if generated_files:
        print(f"\n[SYSTEM_SUCCESS]: Lore extraction complete.")
        print(f"  Files generated: {len(generated_files)}")
        for name, path in generated_files:
            print(f"    • {name}: {path}")
    elif args.dry_run:
        print(f"\n[SYSTEM_LOG]: Dry run complete. {len(batches)} lore file(s) previewed.")


if __name__ == "__main__":
    main()
