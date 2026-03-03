#!/usr/bin/env python3
"""
/* [FILE_ID]: backfill_blog_footer // VERSION: 1.1 // STATUS: STABLE */
Backfill the blog footer onto all existing articles in the
STATUS: UNVERIFIED blog that don't already contain it.

Usage:
    python3 scripts/backfill_blog_footer.py          # append only to articles missing the footer
    python3 scripts/backfill_blog_footer.py --force   # strip old footer and re-apply current version
"""

import argparse
import importlib.util
import os
import re
import sys

# Direct import to avoid triggering agents/skills/__init__.py which pulls heavy deps
_skill_path = os.path.join(os.path.dirname(__file__), "..", "agents", "skills", "shopify_skill", "shopify_skill.py")
_spec = importlib.util.spec_from_file_location("shopify_skill", _skill_path)
_shopify_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shopify_module)
ShopifyConduit = _shopify_module.ShopifyConduit

BLOG_TITLE = "STATUS: UNVERIFIED"
FOOTER_PATH = os.path.join(os.path.dirname(__file__), "..", "artifacts", "templates", "blog_footer.html")
# Unique marker to detect if footer is already present
FOOTER_MARKER = "[NOTICE: EXTERNAL_LAB_ANALYSIS_REQUIRED]"
# Regex to strip the old footer block (from the <hr> before the marker to end of body)
FOOTER_STRIP_RE = re.compile(r'\s*<hr>\s*<p><strong>\[NOTICE: EXTERNAL_LAB_ANALYSIS_REQUIRED\].*', re.DOTALL)


def main():
    parser = argparse.ArgumentParser(description="Backfill blog footer on STATUS: UNVERIFIED articles")
    parser.add_argument("--force", action="store_true", help="Replace existing footer with current version")
    parser.add_argument("--strip-only", action="store_true", help="Remove footer from all articles without re-adding")
    args = parser.parse_args()

    conduit = ShopifyConduit()
    blogs = conduit.list_blogs()
    blog_id = None
    for b in blogs:
        if b.get("title", "").strip() == BLOG_TITLE:
            blog_id = b["id"]
            break

    if not blog_id:
        print(f"!! BLOG_NOT_FOUND: '{BLOG_TITLE}'")
        sys.exit(1)

    print(f"// TARGET_BLOG: {BLOG_TITLE} (ID {blog_id})")

    if args.strip_only:
        print("// MODE: STRIP_ONLY — removing footers from all articles")
        articles = conduit.list_articles(blog_id, limit=250)
        print(f"// ARTICLES_FOUND: {len(articles)}")
        stripped = 0
        for article in articles:
            aid = article["id"]
            title = article.get("title", "?")
            body = article.get("body_html", "") or ""
            if FOOTER_MARKER in body:
                new_body = FOOTER_STRIP_RE.sub("", body)
                conduit.update_article(blog_id, aid, {"body_html": new_body})
                print(f"   [STRIPPED] {aid} — '{title}'")
                stripped += 1
            else:
                print(f"   [SKIP] {aid} — '{title}' (no footer)")
        print(f"\n// STRIP_COMPLETE: {stripped} articles updated")
        return

    footer_path = os.path.normpath(FOOTER_PATH)
    if not os.path.exists(footer_path):
        print(f"!! FOOTER_NOT_FOUND: {footer_path}")
        sys.exit(1)

    with open(footer_path, "r") as f:
        footer_html = f.read()

    conduit = ShopifyConduit()
    blogs = conduit.list_blogs()
    blog_id = None
    for b in blogs:
        if b.get("title", "").strip() == BLOG_TITLE:
            blog_id = b["id"]
            break

    if not blog_id:
        print(f"!! BLOG_NOT_FOUND: '{BLOG_TITLE}'")
        sys.exit(1)

    print(f"// TARGET_BLOG: {BLOG_TITLE} (ID {blog_id})")
    if args.force:
        print("// MODE: FORCE — replacing existing footers with current template")
    articles = conduit.list_articles(blog_id, limit=250)
    print(f"// ARTICLES_FOUND: {len(articles)}")

    updated = 0
    skipped = 0
    for article in articles:
        aid = article["id"]
        title = article.get("title", "?")
        body = article.get("body_html", "") or ""

        has_footer = FOOTER_MARKER in body

        if has_footer and not args.force:
            print(f"   [SKIP] {aid} — '{title}' (footer already present)")
            skipped += 1
            continue

        if has_footer:
            # Strip old footer before re-applying
            body = FOOTER_STRIP_RE.sub("", body)

        new_body = body + footer_html
        conduit.update_article(blog_id, aid, {"body_html": new_body})
        print(f"   [UPDATED] {aid} — '{title}'")
        updated += 1

    print(f"\n// BACKFILL_COMPLETE: {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    main()
