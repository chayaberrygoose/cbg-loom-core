````skill
---
name: printify-catalog
description: Automatically syncs products from Printify into a Markdown catalog. Use when the user wants to update their product list, generate new product pages, or refresh the catalog with the latest images and descriptions.
---

# Printify Catalog Sync

This skill automates the process of fetching products from Printify, downloading images, and generating a linked Markdown catalog.

## Workflow

1.  **Identify Shop ID and Output path**:
    *   Default Shop ID: `12043562`
    *   Default Output Directory: `~/repos/cbg-loom-core/artifacts/catalog`
    *   Requires `PRINTIFY_API_TOKEN` environment variable.

2.  **Execute Sync Script**:
    Run the bundled Python script to perform the cleanup, download, and generation:

    ```bash
    export PRINTIFY_API_TOKEN="your_token_here"
    python3 agents/skills/printify-catalog/scripts/sync_catalog.py <shop_id> artifacts/catalog
    ```

3.  **Resulting Structure**:
    *   `catalog.md`: The main index table with links, publication status, and previews.
    *   `{product_id}/`: Dedicated directory for each product ID.
        *   `{product_name}.md`: Individual detailed product report (includes Status).
        *   `{product_name}_{n}.jpg`: Product images (localized).
    *   `products.json`: The raw data retrieved from the API.

## Notes
- The script automatically cleans up existing product ID directories and `catalog.md` before starting to ensure a clean sync.
- Pipe characters (`|`) in product titles are automatically escaped or replaced with `&#124;` to ensure Markdown table compatibility.
- Image paths are URL-encoded for VSCode compatibility.

## Updating Products
This skill also supports updating existing products. To update a product:
1. **Endpoint**: `PUT https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json`
2. **Permissions**: Requires the `products.write` scope (included in the default token).
3. **Modifiable Fields**:
   - `title`: String
   - `description`: String
   - `tags`: Array of strings
   - `variants`: Array of objects (price, is_enabled, etc.)
   - `print_areas`: Array of objects (designs, placeholders)
4. **Workflow**: Always fetch the current product JSON (`GET`) first to understand the existing structure before sending a `PUT` request with the modified fields.

````
