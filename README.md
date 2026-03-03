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
3. **EXTRUSION:** Graphics are mapped onto a Printify garment template (Hoodie, Joggers, Leggings, Sports Bra, Shorts, Tee, etc.) and published as a product.
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
```

**Programmatic (for agents):**
```python
from scripts.fabricate import run
product = run()  # zero-config
```

## 04_AUTOMATED_FABRICATION

The Loom can run autonomously via cron, extruding one specimen per hour:

```bash
# Install hourly cron job
(crontab -l 2>/dev/null | grep -v fabricate_cron; echo "0 * * * * ~/repos/cbg-loom-core/scripts/fabricate_cron.sh") | crontab -

# Verify
crontab -l

# Remove the job
crontab -l | grep -v fabricate_cron | crontab -

# Monitor logs
tail -f /tmp/cbg_fabricate.log
```

## 06_LORE_ARCHIVE
Lore themes drive every specimen's visual language. Each theme defines a palette, motifs, and prompt modifiers consumed by the Remix Protocol.

| Theme | File |
| :--- | :--- |
| Brutalist Mesh | `artifacts/lore/Brutalist Mesh.md` |
| Gilded Jitter | `artifacts/lore/Gilded Jitter.md` |
| Neon Siphon | `artifacts/lore/Neon Siphon.md` |
| Obsidian Circuit | `artifacts/lore/Obsidian Circuit.md` |
| Phantom Grid | `artifacts/lore/Phantom Grid.md` |
| Sub-Atomic Bloom | `artifacts/lore/Sub-Atomic Bloom.md` |
| Thermal Breach | `artifacts/lore/Thermal Breach.md` |

Add new themes by dropping a `.md` file into `artifacts/lore/` with `## Description`, `## Palette`, `## Motifs`, and `## Prompt Modifiers` sections.

---

## 07_ACCESS_PROTOCOL
* [ ] **Public Terminal:** [chayaberrygoose.com](https://www.chayaberrygoose.com)
* [ ] **Commerce Probe:** [CBG Studio Shopify](https://cbg.studio)
* [ ] **Visual Archive:** [Pinterest](https://pinterest.com/chayaberrygoose)

---

**[STATUS: DATA_FOSSILIZED]**
**[END_OF_MANIFEST]**
