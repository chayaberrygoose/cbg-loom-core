# /* [FILE_ID]: scripts/GENERATE_LORE_FROM_COMMENTS // VERSION: 1.1 // STATUS: STABLE */
# [NARRATIVE]: Extracts Specimen Lore from Shopify blog comments,
#              synthesizes structured lore.md files via Gemini.
# [USAGE]: python scripts/generate_lore_from_comments.py
#          (defaults to Lore Feed post, auto-generates specimen name)

import os
import sys
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

# Ensure the project root is in the path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.skills.shopify_skill.shopify_skill import ShopifyConduit
from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data
from dotenv import load_dotenv

load_dotenv()

# ─── DEFAULT LORE FEED POST ────────────────────────────────────
# Hardcoded until further notice
DEFAULT_BLOG_ID = 104538177748
DEFAULT_ARTICLE_ID = 593820188884

# ─── OUTPUT DIRECTORY ──────────────────────────────────────────
LORE_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "lore"


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


def generate_specimen_name(model, seed_text: str) -> str:
    """
    Use Gemini to generate a creative Industrial Noir specimen name.
    Returns a two-word name in Title Case.
    """
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
        result = generate_specimen_data(model, prompt)
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

    args = parser.parse_args()

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

    # ── Extract Seeds ───────────────────────────────────────────
    seed_text = extract_lore_seeds(comments)
    print(f"[SYSTEM_LOG]: Extracted {len(comments)} comment(s) as seed data.")

    # ── Initialize Gemini ───────────────────────────────────────
    print("[SYSTEM_INIT]: Establishing Gemini Loom Uplink...")
    model = initialize_loom_uplink()
    if not model:
        print("[SYSTEM_DISSONANCE]: Failed to initialize Gemini. Check GOOGLE_API_KEY.")
        sys.exit(1)

    # ── Determine Specimen Name ─────────────────────────────────
    if args.specimen_name:
        specimen_name = args.specimen_name
    else:
        print("[SYSTEM_LOG]: Generating specimen name via Gemini...")
        specimen_name = generate_specimen_name(model, seed_text)
    print(f"[SYSTEM_LOG]: Specimen Name → {specimen_name}")

    # ── Generate Lore ───────────────────────────────────────────
    prompt = generate_lore_prompt(seed_text, specimen_name)
    print("[SYSTEM_LOG]: Synthesizing lore via Gemini...")

    lore_content = generate_specimen_data(model, prompt)

    if lore_content.startswith("[SYSTEM_FAILURE]") or lore_content.startswith("[ACCESS_DENIED]"):
        print(f"[SYSTEM_DISSONANCE]: Lore generation failed — {lore_content}")
        sys.exit(1)

    # ── Output ──────────────────────────────────────────────────
    if args.dry_run:
        print("\n" + "=" * 60)
        print("[DRY_RUN]: Generated Lore Preview")
        print("=" * 60)
        print(lore_content)
        print("=" * 60)
    else:
        filepath = write_lore_file(specimen_name, lore_content)
        print(f"\n[SYSTEM_SUCCESS]: Lore extraction complete.")
        print(f"  Specimen: {specimen_name}")
        print(f"  Output:   {filepath}")


if __name__ == "__main__":
    main()
