# Shopify Skill

Conduit to the Shopify Admin REST API for Blog, Product, and Collection operations.

## Setup

### 1. Create a Custom App in Shopify

1. Go to **Shopify Admin → Settings → Apps and sales channels → Develop apps**.
2. Click **Create an app** and give it a name (e.g. `CBG Loom Integration`).
3. Under **Configuration → Admin API integration**, grant the following scopes:
   - `read_content`, `write_content` — for Blogs, Articles, and Comments
   - `read_products`, `write_products` — for Products
   - `read_publications` — optional, for publish status
4. Click **Install app**.
5. Copy the **Admin API access token** (you only see it once).

### 2. Add credentials to `.env`

```dotenv
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxx
```

## Usage

```python
from agents.skills.shopify_skill import ShopifyConduit

shop = ShopifyConduit()
shop.check_connection()

# ── Blog ───────────────────────────────
blogs = shop.list_blogs()
blog_id = blogs[0]["id"]

shop.create_article(
    blog_id=blog_id,
    title="New Drop: Quantum Topology Hoodie",
    body_html="<p>Available now in the Archive.</p>",
    tags="drop, hoodie, quantum",
)

shop.list_articles(blog_id)

# ── Comments ───────────────────────────
shop.list_comments(blog_id=blog_id)  # published comments
shop.list_comments(status="pending") # pending moderation

# ── Products ───────────────────────────
shop.list_products()

# ── Collections ────────────────────────
shop.list_custom_collections()
```

## Quick Test

```bash
cd ~/repos/cbg-loom-core
export PYTHONPATH=$PYTHONPATH:.
python3 agents/skills/shopify_skill/shopify_skill.py
```
