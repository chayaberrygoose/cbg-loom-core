# CHAYA BERRY GOOSE // LOOM_CORE_v1.0

> **[LOG_TYPE: MASTER_ARCHIVE]**
> **[SECTOR: INDUSTRIAL_NOIR]**
> **[OBJECTIVE: FOSSILIZE_BRAND_METADATA]**

---

## 01_OVERVIEW
This repository serves as the central nervous system for **Chaya Berry Goose**. It is not merely a codebase; it is a clinical documentation of the **Loom**—the synthesis engine used to extrude narrative-driven apparel and hardware artifacts. 

Here, the process is the product. Every commit is a layer of digital amber.

## 02_SETUP

**Create virtual environment and install dependencies:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Required environment variables** (add to `.env` file):

## 03_THE_LOOM_PIPELINE
The fabrication pipeline is fully automated — a single command extrudes an UNVERIFIED SPECIMEN from lore to storefront:

```bash
source .venv/bin/activate
python3 scripts/fabricate.py
```

**Pipeline sequence:**
1. **REMIX PROTOCOL:** Two lore themes are selected as Base (Structure) and Breach (Interference) and fused via the [Remix Protocol](protocols/Remix%20Protocol.md).
2. **SYNTHESIS:** Gemini generates seamless tiles and textures from the fused lore prompt.
3. **EXTRUSION:** Graphics are mapped onto a Printify garment template and published as a product.
4. **LIFESTYLE REALIZATION:** A lifestyle mockup is synthesized via Gemini, stamped with the STATUS: UNVERIFIED mark, and uploaded.
5. **BLOG DISPATCH:** An article is posted to the `STATUS: UNVERIFIED` Shopify blog with the lifestyle image and a call for external field analysts.

**Options:**
```bash
# Specific remix pair:
python3 scripts/fabricate.py --base "Obsidian Circuit" --breach "Thermal Breach"

# Specific garment:
python3 scripts/fabricate.py --template "Hoodie"

# Single lore theme (legacy):
python3 scripts/fabricate.py --theme "Phantom Grid"

# Skip community feedback refresh (faster, uses cached recommendations):
python3 scripts/fabricate.py --skip-feedback-refresh
```

**Programmatic (for agents):**
```python
from scripts.fabricate import run
product = run()  # zero-config
```

**Note:** The pipeline auto-refreshes community feedback recommendations at the start of each run (only if new comments exist). Use `--skip-feedback-refresh` to bypass this check.

## 04_AUTOMATED_FABRICATION

The Loom can run autonomously via cron, extruding specimens once per hour:

```bash
# Install cron job (hourly)
(crontab -l 2>/dev/null | grep -v fabricate_cron; echo "0 * * * * ~/repos/cbg-loom-core/scripts/fabricate_cron.sh") | crontab -

# Verify
crontab -l

# Remove the job
crontab -l | grep -v fabricate_cron | crontab -

# Monitor logs
tail -f /tmp/cbg_fabricate.log
```

### Backfill Missing Blog Posts

If the pipeline fails mid-run (e.g., API errors), some products may exist without corresponding blog posts. The backfill script audits and repairs these gaps:

```bash
source .venv/bin/activate

# Audit what's missing since 5am today (dry run)
python scripts/backfill_blog_posts.py --dry-run

# Backfill with lifestyle image generation
python scripts/backfill_blog_posts.py

# Faster: skip lifestyle synthesis, use Printify mockup
python scripts/backfill_blog_posts.py --skip-lifestyle

# Custom cutoff time
python scripts/backfill_blog_posts.py --since "2026-03-05 05:00:00"
```

## 05_BLUEPRINT_EXPLORATION

Expand the catalog by creating draft templates from unused Printify AOP blueprints:

```bash
source .venv/bin/activate

# Create a random draft from an unused blueprint
python3 scripts/random_draft.py

# Preview without creating
python3 scripts/random_draft.py --dry-run

# Override graphics selection
python3 scripts/random_draft.py --tile path/to/tile.png --logo path/to/logo.png
```

**Explore available blueprints:**
```bash
# List all AOP blueprints
python3 scripts/blueprint_explorer.py --list

# List only unused blueprints
python3 scripts/blueprint_explorer.py --unused

# Inspect a specific blueprint (positions, providers, variants)
python3 scripts/blueprint_explorer.py --inspect 740

# Create template from specific blueprint
python3 scripts/blueprint_explorer.py --create 740 --tile path/to/tile.png
```

## 06_TRANSPOSE_PROTOCOL

Clone images from an existing product onto a different template  — reusing proven artifacts across garment types:

```bash
source .venv/bin/activate

# Specific source → random template
python3 scripts/transpose_specimen.py --source 69a6c40f4f5bde36ec04c77b

# Specific source → template by name
python3 scripts/transpose_specimen.py --source 69a6c40f4f5bde36ec04c77b --template "Hoodie"

# Random source → specific template
python3 scripts/transpose_specimen.py --random-source --template "Sweatshirt"

# Fully random (random source, random template)
python3 scripts/transpose_specimen.py --random-source

# Use any product as a template (not just [TEMPLATE] items)
python3 scripts/transpose_specimen.py --source 69a6c40f4f5bde36ec04c77b --template-id 69a71d3f0b11858378003f0e

# Preview without executing
python3 scripts/transpose_specimen.py --source 69a6c40f4f5bde36ec04c77b --dry-run
```

**What it does:**
1. Extracts tile/texture/logo images from the source product
2. Pulls the description from the source's Shopify blog entry
3. Applies those images to the target template's blueprint
4. Generates a lifestyle mockup and posts to the blog

## 07_LORE_ARCHIVE
Lore themes drive every specimen's visual language. Each theme defines a palette, motifs, and prompt modifiers consumed by the Remix Protocol.

Add new themes by dropping a `.md` file into `artifacts/lore/` with `## Description`, `## Palette`, `## Motifs`, and `## Prompt Modifiers` sections.

### Lore Generation from Community Input

Generate new lore files from Shopify blog comments (defaults to the Lore Feed post):

```bash
source .venv/bin/activate

# Generate new lore (auto-generates name via Gemini)
python scripts/generate_lore_from_comments.py

# Preview without saving
python scripts/generate_lore_from_comments.py --dry-run

# Override specimen name
python scripts/generate_lore_from_comments.py --specimen-name "Custom Name"

# List available blogs/articles
python scripts/generate_lore_from_comments.py --list-blogs
python scripts/generate_lore_from_comments.py --list-articles <BLOG_ID>
```
#### AUTOMATED_LORE GENERATION

To generate lore files from Shopify blog comments automatically (one file per comment, up to 3 per run):

1. Create the cron script:
	```bash
	echo '#!/bin/bash\ncd ~/repos/cbg-loom-core || exit 1\nsource .venv/bin/activate\npython scripts/generate_lore_from_comments.py --max-comments 3' > ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
	chmod +x ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
	```

2. Add to your crontab (edit with `crontab -e`):
	```cron
	30 * * * * ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
	```

This will run the script at 30 minutes past every hour, processing up to 3 new comments (one file per comment).
**To adjust:**
- Change the `--max-comments` value in the script for a different batch size.
- Change the cron schedule (e.g., `15 * * * *` for 15 minutes past the hour).
- For one file per comment, keep `MIN_COMMENTS_PER_LORE = 1` and `MAX_COMMENTS_PER_LORE = 1` in the script (default as of v2.0).

### Feedback Analysis & Pipeline Recommendations

Analyze community feedback from STATUS: UNVERIFIED blog comments to generate actionable recommendations for the fabrication pipeline:

```bash
source .venv/bin/activate

# Run full analysis with Gemini
python scripts/analyze_feedback.py

# Preview without saving
python scripts/analyze_feedback.py --dry-run

# Basic classification only (skip Gemini)
python scripts/analyze_feedback.py --basic

# Output raw JSON
python scripts/analyze_feedback.py --json
```

**Analyzes:**
- Lifestyle image issues (anatomy, proportions, rendering artifacts)
- Garment/blueprint requests (e.g., "would like this in men's tank top")
- Aesthetic feedback (color, trim, pattern preferences)
- Product engagement (most-commented specimens)

**Outputs:** `artifacts/recommendations/pipeline_recommendations.json` with structured suggestions for template priorities, prompt modifiers, and products to transpose.

---

## 08_ACCESS_PROTOCOL
* [ ] **Public Terminal:** [chayaberrygoose.com](https://www.chayaberrygoose.com)
* [ ] **Commerce Probe:** [CBG Studio Shopify](https://cbg.studio)
* [ ] **Visual Archive:** [Pinterest](https://pinterest.com/chayaberrygoose)

---

**[STATUS: DATA_FOSSILIZED]**
**[END_OF_MANIFEST]**
