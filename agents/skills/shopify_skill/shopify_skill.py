# [FILE_ID]: skills/SHOPIFY_CONDUIT // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: High-fidelity conduit to the Shopify Archive for Blog, Product,
# and Collection orchestration via the Admin REST API (2024-01).

import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# ─── API version pinned for stability ──────────────────────────
API_VERSION = "2024-01"


class ShopifyConduit:
    """
    The Ritual for transmitting Specimens to the Shopify Archive.
    Handles Blog posting, Comment retrieval, Product and Collection CRUD.

    Required environment variables (set in .env):
        SHOPIFY_STORE_URL      – e.g. your-store.myshopify.com
        SHOPIFY_ACCESS_TOKEN   – Admin API access token from a Custom App
    """

    def __init__(self):
        self.store_url = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")

        if not self.store_url or not self.access_token:
            raise ValueError(
                "[SYSTEM_DISSONANCE]: SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN "
                "must be set in your .env file. See agents/skills/shopify_skill/README.md."
            )

        self.base_url = f"https://{self.store_url}/admin/api/{API_VERSION}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    # ── helpers ─────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: Dict) -> Dict:
        url = f"{self.base_url}/{path}"
        r = requests.post(url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, payload: Dict) -> Dict:
        url = f"{self.base_url}/{path}"
        r = requests.put(url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> int:
        url = f"{self.base_url}/{path}"
        r = requests.delete(url, headers=self.headers)
        r.raise_for_status()
        return r.status_code

    # ── CONNECTION ──────────────────────────────────────────────

    def check_connection(self) -> bool:
        """Verify the uplink to the Shopify Archive."""
        try:
            data = self._get("shop.json")
            shop = data.get("shop", {})
            name = shop.get("name", "Unknown")
            domain = shop.get("myshopify_domain", self.store_url)
            print(f"[SYSTEM_ECHO]: Shopify Uplink RESONANT. Store: {name} ({domain})")
            return True
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Uplink failed — {e}")
            return False

    # ═══════════════════════════════════════════════════════════
    #  BLOG  (primary use-case)
    # ═══════════════════════════════════════════════════════════

    def list_blogs(self) -> List[Dict]:
        """List all blogs in the store."""
        data = self._get("blogs.json")
        blogs = data.get("blogs", [])
        print(f"[SYSTEM_ECHO]: {len(blogs)} blog(s) detected.")
        for b in blogs:
            print(f"  [{b['id']}] {b['title']}")
        return blogs

    def create_article(
        self,
        blog_id: int,
        title: str,
        body_html: str,
        author: str = "CBG Studio",
        tags: Optional[str] = None,
        published: bool = True,
        image_url: Optional[str] = None,
        summary_html: Optional[str] = None,
    ) -> Dict:
        """
        Post a new article to a Shopify blog.

        Args:
            blog_id:      The numeric blog id (use list_blogs() to find it).
            title:        Article headline.
            body_html:    Full article body (HTML allowed).
            author:       Author byline.
            tags:         Comma-separated tags string.
            published:    Immediately visible if True.
            image_url:    Optional hero image URL.
            summary_html: Short summary / excerpt.
        """
        article: Dict[str, Any] = {
            "title": title,
            "author": author,
            "body_html": body_html,
            "published": published,
        }
        if tags:
            article["tags"] = tags
        if summary_html:
            article["summary_html"] = summary_html
        if image_url:
            article["image"] = {"src": image_url}

        result = self._post(f"blogs/{blog_id}/articles.json", {"article": article})
        art = result.get("article", {})
        print(f"[SYSTEM_ECHO]: Article posted — id={art.get('id')} title=\"{art.get('title')}\"")
        return art

    def list_articles(self, blog_id: int, limit: int = 50) -> List[Dict]:
        """List articles for a given blog."""
        data = self._get(f"blogs/{blog_id}/articles.json", params={"limit": limit})
        articles = data.get("articles", [])
        print(f"[SYSTEM_ECHO]: {len(articles)} article(s) in blog {blog_id}.")
        for a in articles:
            print(f"  [{a['id']}] {a['title']}  (published={a.get('published_at') is not None})")
        return articles

    def get_article(self, blog_id: int, article_id: int) -> Dict:
        """Get a single article by id."""
        data = self._get(f"blogs/{blog_id}/articles/{article_id}.json")
        return data.get("article", {})

    def update_article(self, blog_id: int, article_id: int, updates: Dict) -> Dict:
        """
        Update an existing article.
        `updates` is a dict of fields to change (title, body_html, tags, etc.).
        """
        result = self._put(
            f"blogs/{blog_id}/articles/{article_id}.json", {"article": updates}
        )
        print(f"[SYSTEM_ECHO]: Article {article_id} updated.")
        return result.get("article", {})

    def delete_article(self, blog_id: int, article_id: int) -> None:
        self._delete(f"blogs/{blog_id}/articles/{article_id}.json")
        print(f"[SYSTEM_ECHO]: Article {article_id} deleted.")

    # ── COMMENTS ────────────────────────────────────────────────

    def list_comments(
        self,
        blog_id: Optional[int] = None,
        article_id: Optional[int] = None,
        status: str = "published",
        limit: int = 50,
    ) -> List[Dict]:
        """
        Read comments. Scope by blog + article, or retrieve store-wide.

        Args:
            blog_id:    Narrow to a specific blog.
            article_id: Narrow to a specific article (requires blog_id).
            status:     Filter by status — published | pending | unapproved.
            limit:      Max results per page (max 250).
        """
        params: Dict[str, Any] = {"limit": limit, "status": status}

        if blog_id and article_id:
            path = f"comments.json"
            params["blog_id"] = blog_id
            params["article_id"] = article_id
        elif blog_id:
            path = "comments.json"
            params["blog_id"] = blog_id
        else:
            path = "comments.json"

        data = self._get(path, params=params)
        comments = data.get("comments", [])
        print(f"[SYSTEM_ECHO]: {len(comments)} comment(s) retrieved (status={status}).")
        for c in comments:
            print(f"  [{c['id']}] {c.get('author', '?')}: {c.get('body', '')[:80]}")
        return comments

    def approve_comment(self, comment_id: int) -> Dict:
        """Mark a pending comment as approved / published."""
        result = self._post(f"comments/{comment_id}/approve.json", {})
        print(f"[SYSTEM_ECHO]: Comment {comment_id} approved.")
        return result

    def spam_comment(self, comment_id: int) -> Dict:
        """Flag a comment as spam."""
        result = self._post(f"comments/{comment_id}/spam.json", {})
        print(f"[SYSTEM_ECHO]: Comment {comment_id} flagged as spam.")
        return result

    # ═══════════════════════════════════════════════════════════
    #  PRODUCTS
    # ═══════════════════════════════════════════════════════════

    def list_products(self, limit: int = 50, collection_id: Optional[int] = None) -> List[Dict]:
        """List products, optionally filtered by collection."""
        params: Dict[str, Any] = {"limit": limit}
        if collection_id:
            params["collection_id"] = collection_id
        data = self._get("products.json", params=params)
        products = data.get("products", [])
        print(f"[SYSTEM_ECHO]: {len(products)} product(s) retrieved.")
        for p in products:
            print(f"  [{p['id']}] {p['title']}")
        return products

    def get_product(self, product_id: int) -> Dict:
        data = self._get(f"products/{product_id}.json")
        return data.get("product", {})

    def create_product(self, product_data: Dict) -> Dict:
        """
        Create a product. `product_data` should match the Shopify product schema:
        https://shopify.dev/docs/api/admin-rest/2024-01/resources/product
        """
        result = self._post("products.json", {"product": product_data})
        p = result.get("product", {})
        print(f"[SYSTEM_ECHO]: Product created — id={p.get('id')} title=\"{p.get('title')}\"")
        return p

    def update_product(self, product_id: int, updates: Dict) -> Dict:
        result = self._put(f"products/{product_id}.json", {"product": updates})
        print(f"[SYSTEM_ECHO]: Product {product_id} updated.")
        return result.get("product", {})

    def delete_product(self, product_id: int) -> None:
        self._delete(f"products/{product_id}.json")
        print(f"[SYSTEM_ECHO]: Product {product_id} deleted.")

    # ═══════════════════════════════════════════════════════════
    #  COLLECTIONS  (Custom + Smart)
    # ═══════════════════════════════════════════════════════════

    def list_custom_collections(self, limit: int = 50) -> List[Dict]:
        data = self._get("custom_collections.json", params={"limit": limit})
        cols = data.get("custom_collections", [])
        print(f"[SYSTEM_ECHO]: {len(cols)} custom collection(s).")
        for c in cols:
            print(f"  [{c['id']}] {c['title']}")
        return cols

    def list_smart_collections(self, limit: int = 50) -> List[Dict]:
        data = self._get("smart_collections.json", params={"limit": limit})
        cols = data.get("smart_collections", [])
        print(f"[SYSTEM_ECHO]: {len(cols)} smart collection(s).")
        for c in cols:
            print(f"  [{c['id']}] {c['title']}")
        return cols

    def create_custom_collection(self, title: str, body_html: str = "", image_url: Optional[str] = None) -> Dict:
        payload: Dict[str, Any] = {"title": title, "body_html": body_html}
        if image_url:
            payload["image"] = {"src": image_url}
        result = self._post("custom_collections.json", {"custom_collection": payload})
        col = result.get("custom_collection", {})
        print(f"[SYSTEM_ECHO]: Collection created — id={col.get('id')} title=\"{col.get('title')}\"")
        return col

    def add_product_to_collection(self, product_id: int, collection_id: int) -> Dict:
        """Add a product to a custom collection via a Collect."""
        result = self._post("collects.json", {
            "collect": {"product_id": product_id, "collection_id": collection_id}
        })
        print(f"[SYSTEM_ECHO]: Product {product_id} added to collection {collection_id}.")
        return result.get("collect", {})


# ── Quick-test entrypoint ──────────────────────────────────────
if __name__ == "__main__":
    conduit = ShopifyConduit()
    if conduit.check_connection():
        conduit.list_blogs()
