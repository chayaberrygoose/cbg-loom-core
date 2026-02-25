---
name: printify-catalog
description: Automatically syncs products from Printify into a Markdown catalog. Use when the user wants to update their product list, generate new product pages, or refresh the catalog with the latest images and descriptions.
---

# Printify Catalog Sync

This skill automates the process of fetching products from Printify, downloading images, and generating a linked Markdown catalog.

## Workflow

1.  **Identify Shop ID and Token Path**:
    *   Default Shop ID: `12043562`
    *   Default Token Path: `/home/cbg/repos/cbg/prinitfy_api_token.txt`
    *   Default Output Directory: `/home/cbg/repos/cbg`

2.  **Execute Sync Script**:
    Run the bundled Python script to perform the cleanup, download, and generation:

    ```bash
    python3 scripts/sync_catalog.py <shop_id> <token_path> <output_dir>
    ```

3.  **Resulting Structure**:
    *   `catalog.md`: The main index table with links and image previews.
    *   `products_md/`: Individual detailed Markdown files for each product.
    *   `Product images/`: All downloaded product images (up to 2 per product).
    *   `products.json`: The raw data retrieved from the API.

## Notes
- The script automatically deletes the existing `catalog.md`, `products_md/`, and `Product images/` before starting to ensure a clean sync.
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
