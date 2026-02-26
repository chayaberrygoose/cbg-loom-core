# Fabricator Protocol (Printify Product Cloning)

This module provides the logic for "cloning" a Printify product's schematic (blueprint, print provider, and print area positioning) while injecting a new media asset (swatch).

## Usage

```python
from agents.skills.fabricator.fabricator import Fabricator

# Initialize
fabricator = Fabricator()

# Clone a product with a new image URL
new_product = fabricator.clone_product(
    source_product_id="699abcd0c7c3be94ff0c20ad",
    new_image_url="https://example.com/new_swatch.png",
    title_suffix=" - New Variant"
)
```

## Protocol Details

1.  **Ingest Specimen**: Retrieves the source product JSON.
2.  **Upload Artifact**: Uploads the `new_image_url` to the Printify Media Library.
3.  **Construct Schematic**: 
    - Copies `blueprint_id` and `print_provider_id`.
    - Iterates through `print_areas`.
    - Preserves `x`, `y`, `scale`, `angle` for `placeholders`.
    - Swaps the image `id` with the new upload.
4.  **Fabricate**: POSTs the new payload to create the product.
