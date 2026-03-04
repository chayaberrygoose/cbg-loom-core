# /* [FILE_ID]: scripts/ANALYZE_FEEDBACK // VERSION: 1.0 // STATUS: STABLE */
# [NARRATIVE]: Extracts community feedback from STATUS: UNVERIFIED blog comments,
#              analyzes sentiment and generates actionable pipeline recommendations.
# [USAGE]: python scripts/analyze_feedback.py

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.skills.shopify_skill.shopify_skill import ShopifyConduit
from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data
from dotenv import load_dotenv

load_dotenv()

# ─── CONSTANTS ─────────────────────────────────────────────────
STATUS_UNVERIFIED_BLOG_ID = 104482537684
RECOMMENDATIONS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "recommendations"
RECOMMENDATIONS_FILE = RECOMMENDATIONS_DIR / "pipeline_recommendations.json"

# Feedback category patterns (basic classification before Gemini)
APPROVAL_PATTERNS = [
    r"i like this",
    r"looks? good",
    r"interesting",
    r"cool",
    r"nice",
    r"love it",
    r"amazing",
    r"great",
]

LIFESTYLE_ISSUE_PATTERNS = [
    r"weird",
    r"wrong",
    r"doesn't look right",
    r"legs?",
    r"arms?",
    r"hands?",
    r"body",
    r"proportion",
    r"anatomy",
    r"cut off",
    r"missing",
    r"floating",
]

GARMENT_PATTERNS = [
    r"trim",
    r"color",
    r"black",
    r"white",
    r"tank\s?top",
    r"hoodie",
    r"t-?shirt",
    r"jogger",
    r"legging",
    r"dress",
    r"skirt",
    r"apron",
    r"sweatshirt",
    r"men'?s",
    r"women'?s",
]

AESTHETIC_PATTERNS = [
    r"pattern",
    r"color",
    r"palette",
    r"texture",
    r"design",
    r"motif",
    r"bright",
    r"dark",
    r"contrast",
]


def extract_product_id_from_title(title: str) -> Optional[str]:
    """Extract Printify product ID from article title."""
    match = re.search(r'UNVERIFIED SPECIMEN:\s*([a-f0-9]{24})', title, re.IGNORECASE)
    return match.group(1) if match else None


def classify_feedback_basic(body: str) -> Dict[str, bool]:
    """
    Basic regex classification of feedback type.
    Returns dict of category flags.
    """
    body_lower = body.lower()
    
    return {
        "is_approval": any(re.search(p, body_lower) for p in APPROVAL_PATTERNS),
        "has_lifestyle_issue": any(re.search(p, body_lower) for p in LIFESTYLE_ISSUE_PATTERNS),
        "has_garment_feedback": any(re.search(p, body_lower) for p in GARMENT_PATTERNS),
        "has_aesthetic_feedback": any(re.search(p, body_lower) for p in AESTHETIC_PATTERNS),
    }


def fetch_all_feedback(conduit: ShopifyConduit) -> List[Dict]:
    """
    Fetch all comments from STATUS: UNVERIFIED blog,
    enriched with article metadata.
    """
    print("[SIGNAL_RECOVERY]: Fetching feedback from STATUS: UNVERIFIED blog...")
    
    comments = conduit.list_comments(
        blog_id=STATUS_UNVERIFIED_BLOG_ID,
        status="published",
        limit=250,
    )
    
    # Group comments by article
    article_cache = {}
    enriched_comments = []
    
    for comment in comments:
        article_id = comment.get("article_id")
        
        # Fetch article metadata if not cached
        if article_id and article_id not in article_cache:
            try:
                article = conduit.get_article(STATUS_UNVERIFIED_BLOG_ID, article_id)
                article_cache[article_id] = {
                    "title": article.get("title", ""),
                    "product_id": extract_product_id_from_title(article.get("title", "")),
                    "image_url": article.get("image", {}).get("src"),
                    "body_excerpt": article.get("body_html", "")[:500],
                }
            except Exception as e:
                print(f"[SYSTEM_WARNING]: Failed to fetch article {article_id}: {e}")
                article_cache[article_id] = None
        
        article_meta = article_cache.get(article_id, {}) or {}
        
        # Basic classification
        body = comment.get("body", "")
        classification = classify_feedback_basic(body)
        
        enriched_comments.append({
            "comment_id": comment.get("id"),
            "article_id": article_id,
            "product_id": article_meta.get("product_id"),
            "image_url": article_meta.get("image_url"),
            "article_title": article_meta.get("title"),
            "author": comment.get("author", "Anonymous"),
            "body": body,
            "created_at": comment.get("created_at"),
            **classification,
        })
    
    return enriched_comments


def aggregate_feedback(comments: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate feedback into summary statistics and groupings.
    """
    stats = {
        "total_comments": len(comments),
        "approvals": 0,
        "lifestyle_issues": [],
        "garment_requests": [],
        "aesthetic_feedback": [],
        "product_popularity": defaultdict(int),
        "product_feedback": defaultdict(list),
    }
    
    for c in comments:
        product_id = c.get("product_id")
        body = c.get("body", "")
        
        if product_id:
            stats["product_popularity"][product_id] += 1
            stats["product_feedback"][product_id].append(body)
        
        if c.get("is_approval") and not any([
            c.get("has_lifestyle_issue"),
            c.get("has_garment_feedback"),
            c.get("has_aesthetic_feedback"),
        ]):
            stats["approvals"] += 1
        
        if c.get("has_lifestyle_issue"):
            stats["lifestyle_issues"].append({
                "product_id": product_id,
                "comment": body,
                "image_url": c.get("image_url"),
            })
        
        if c.get("has_garment_feedback"):
            stats["garment_requests"].append({
                "product_id": product_id,
                "comment": body,
            })
        
        if c.get("has_aesthetic_feedback"):
            stats["aesthetic_feedback"].append({
                "product_id": product_id,
                "comment": body,
            })
    
    # Convert defaultdicts to regular dicts for JSON serialization
    stats["product_popularity"] = dict(stats["product_popularity"])
    stats["product_feedback"] = dict(stats["product_feedback"])
    
    return stats


def generate_recommendations_prompt(aggregated: Dict[str, Any], comments: List[Dict]) -> str:
    """
    Build Gemini prompt for recommendation synthesis.
    """
    # Build context from feedback
    lifestyle_issues_text = "\n".join([
        f"- Product {i['product_id']}: \"{i['comment']}\""
        for i in aggregated["lifestyle_issues"][:10]
    ]) or "None reported"
    
    garment_requests_text = "\n".join([
        f"- \"{r['comment']}\""
        for r in aggregated["garment_requests"][:10]
    ]) or "None reported"
    
    aesthetic_feedback_text = "\n".join([
        f"- \"{f['comment']}\""
        for f in aggregated["aesthetic_feedback"][:10]
    ]) or "None reported"
    
    # Top products by engagement
    top_products = sorted(
        aggregated["product_popularity"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    top_products_text = "\n".join([
        f"- {pid}: {count} comments"
        for pid, count in top_products
    ]) or "No engagement data"
    
    return f"""You are an AI analyst for "Chaya Berry Goose" (CBG Studio), an Industrial Noir / Tech-Wear brand.

Analyze the following community feedback from the STATUS: UNVERIFIED blog and generate actionable recommendations for the automated Loom fabrication pipeline.

## FEEDBACK SUMMARY
- Total comments: {aggregated['total_comments']}
- Simple approvals ("I like this"): {aggregated['approvals']}

## LIFESTYLE IMAGE ISSUES
{lifestyle_issues_text}

## GARMENT/BLUEPRINT REQUESTS
{garment_requests_text}

## AESTHETIC FEEDBACK (patterns, colors)
{aesthetic_feedback_text}

## PRODUCT ENGAGEMENT (most commented)
{top_products_text}

---

Generate a JSON object with the following structure. Output ONLY valid JSON, no markdown code blocks:

{{
  "generated_at": "<ISO timestamp>",
  "summary": "<2-3 sentence summary of overall feedback trends>",
  "recommendations": {{
    "lifestyle_image_improvements": [
      {{
        "issue": "<specific issue description>",
        "action": "<recommended prompt modifier or generation setting>",
        "priority": "high|medium|low"
      }}
    ],
    "garment_priorities": [
      {{
        "garment_type": "<e.g., tank top, hoodie>",
        "reason": "<why this was requested>",
        "template_search": "<search term for pipeline>"
      }}
    ],
    "aesthetic_adjustments": [
      {{
        "adjustment": "<color/pattern suggestion>",
        "applies_to": "all|specific lore themes",
        "details": "<implementation guidance>"
      }}
    ],
    "popular_products": [
      {{
        "product_id": "<id>",
        "engagement_score": <number>,
        "recommendation": "<e.g., transpose to new templates>"
      }}
    ]
  }},
  "pipeline_config_suggestions": {{
    "avoid_garments": ["<list of template types to deprioritize>"],
    "prefer_garments": ["<list of template types to prioritize>"],
    "prompt_modifiers_add": ["<new modifiers to include>"],
    "prompt_modifiers_avoid": ["<modifiers causing issues>"]
  }}
}}
"""


def analyze_with_gemini(aggregated: Dict[str, Any], comments: List[Dict]) -> Dict:
    """
    Use Gemini to synthesize recommendations from aggregated feedback.
    """
    print("[SYSTEM_INIT]: Establishing Gemini Loom Uplink...")
    model = initialize_loom_uplink()
    
    if not model:
        print("[SYSTEM_DISSONANCE]: Failed to initialize Gemini. Returning basic analysis.")
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": "Gemini unavailable. Basic analysis only.",
            "raw_stats": aggregated,
        }
    
    prompt = generate_recommendations_prompt(aggregated, comments)
    print("[SYSTEM_LOG]: Synthesizing recommendations via Gemini...")
    
    response = generate_specimen_data(model, prompt)
    
    if response.startswith("[SYSTEM_FAILURE]") or response.startswith("[ACCESS_DENIED]"):
        print(f"[SYSTEM_WARNING]: Gemini analysis failed: {response}")
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": "Analysis failed.",
            "raw_stats": aggregated,
        }
    
    # Parse JSON from response
    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```json?\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)
        
        recommendations = json.loads(cleaned)
        recommendations["raw_stats"] = {
            "total_comments": aggregated["total_comments"],
            "approvals": aggregated["approvals"],
            "lifestyle_issues_count": len(aggregated["lifestyle_issues"]),
            "garment_requests_count": len(aggregated["garment_requests"]),
            "aesthetic_feedback_count": len(aggregated["aesthetic_feedback"]),
        }
        return recommendations
    except json.JSONDecodeError as e:
        print(f"[SYSTEM_WARNING]: Failed to parse Gemini response as JSON: {e}")
        print(f"[DEBUG]: Response was: {response[:500]}")
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": "JSON parsing failed.",
            "raw_response": response,
            "raw_stats": aggregated,
        }


def save_recommendations(recommendations: Dict) -> Path:
    """
    Save recommendations to JSON file.
    """
    RECOMMENDATIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(RECOMMENDATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(recommendations, f, indent=2, default=str)
    
    print(f"[SYSTEM_ECHO]: Recommendations written → {RECOMMENDATIONS_FILE}")
    return RECOMMENDATIONS_FILE


def print_summary(recommendations: Dict):
    """
    Print human-readable summary.
    """
    print("\n" + "=" * 60)
    print("[FEEDBACK ANALYSIS REPORT]")
    print("=" * 60)
    
    print(f"\nSummary: {recommendations.get('summary', 'N/A')}")
    
    recs = recommendations.get("recommendations", {})
    
    # Lifestyle improvements
    lifestyle = recs.get("lifestyle_image_improvements", [])
    if lifestyle:
        print(f"\n[LIFESTYLE IMAGE ISSUES] ({len(lifestyle)} found)")
        for item in lifestyle[:3]:
            print(f"  • {item.get('issue', 'N/A')}")
            print(f"    Action: {item.get('action', 'N/A')}")
    
    # Garment priorities
    garments = recs.get("garment_priorities", [])
    if garments:
        print(f"\n[GARMENT REQUESTS] ({len(garments)} found)")
        for item in garments[:3]:
            print(f"  • {item.get('garment_type', 'N/A')}: {item.get('reason', '')}")
    
    # Config suggestions
    config = recommendations.get("pipeline_config_suggestions", {})
    if config.get("prefer_garments"):
        print(f"\n[PRIORITIZE TEMPLATES]: {', '.join(config['prefer_garments'])}")
    if config.get("avoid_garments"):
        print(f"[DEPRIORITIZE TEMPLATES]: {', '.join(config['avoid_garments'])}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="[FEEDBACK_ANALYST]: Analyze STATUS: UNVERIFIED comments for pipeline recommendations."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show analysis without saving",
    )
    parser.add_argument(
        "--basic",
        action="store_true",
        help="Skip Gemini analysis, use basic classification only",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )
    
    args = parser.parse_args()
    
    # Initialize Shopify
    print("[SYSTEM_INIT]: Establishing Shopify Uplink...")
    try:
        conduit = ShopifyConduit()
        conduit.check_connection()
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Failed to connect to Shopify — {e}")
        sys.exit(1)
    
    # Fetch and analyze feedback
    comments = fetch_all_feedback(conduit)
    
    if not comments:
        print("[SYSTEM_WARNING]: No comments found. Cannot generate recommendations.")
        sys.exit(1)
    
    print(f"[SYSTEM_LOG]: Fetched {len(comments)} comment(s) for analysis.")
    
    # Aggregate
    aggregated = aggregate_feedback(comments)
    
    # Generate recommendations
    if args.basic:
        recommendations = {
            "generated_at": datetime.now().isoformat(),
            "summary": "Basic classification only (Gemini skipped).",
            "raw_stats": aggregated,
        }
    else:
        recommendations = analyze_with_gemini(aggregated, comments)
    
    # Output
    if args.json:
        print(json.dumps(recommendations, indent=2, default=str))
    else:
        print_summary(recommendations)
    
    if not args.dry_run:
        save_recommendations(recommendations)
        print(f"\n[SYSTEM_SUCCESS]: Feedback analysis complete.")
        print(f"  Recommendations saved to: {RECOMMENDATIONS_FILE}")


if __name__ == "__main__":
    main()
