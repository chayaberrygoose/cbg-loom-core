#!/usr/bin/env python3
# /* [FILE_ID]: scripts/GENERATE_LORE_FROM_NEWS // VERSION: 1.0 // STATUS: STABLE */
# [NARRATIVE]: Scrapes stable real-time news and space weather feeds, then uses Gemini 
#              to synthesize active simulation lore (Incident Brief / World-State Delta)
#              directly inside the artifacts/lore/ directory.
# [USAGE]: python3 scripts/generate_lore_from_news.py

import os
import sys
import re
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
import html

import requests

# Ensure project root is in the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data

# ─── NEWS FEEDS CONFIGURATION ─────────────────────────────────
FEEDS = {
    "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Hacker News": "https://news.ycombinator.com/rss",
    "NASA Breaking News": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "Slashdot": "http://rss.slashdot.org/Slashdot/slashdotMain"
}

NOAA_ALERTS_URL = "https://services.swpc.noaa.gov/products/alerts.json"

def fetch_rss_feed(name: str, url: str, max_items: int = 4) -> list:
    """Fetch and parse RSS feed, return list of {title, description, source}."""
    print(f"[SYSTEM_LOG]: Ingesting feed signals from: {name} …")
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        
        # Clean response text from potential weird characters/bytes
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title_el = item.find("title")
            desc_el = item.find("description")
            
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
            
            # Clean HTML tags and entities
            title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
            desc = re.sub(r"<[^>]+>", "", html.unescape(desc)).strip()
            
            if title:
                items.append({
                    "title": title,
                    "description": desc,
                    "source": name
                })
        return items
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Feed disruption on {name} — {e}")
        return []

def fetch_noaa_alerts() -> str:
    """Fetch space weather alerts from NOAA SWPC (JSON format)."""
    print("[SYSTEM_LOG]: Ingesting NOAA Space Weather telemetry …")
    try:
        resp = requests.get(NOAA_ALERTS_URL, timeout=12)
        resp.raise_for_status()
        alerts = resp.json()
        messages = []
        # Grab first 4 active alerts to avoid prompt bloating
        for alert in alerts[:4]:
            msg = alert.get("message", "").strip()
            # Clean repetitive/technical metadata to keep lore focused
            msg = re.sub(r"(Space Weather Message Code|Serial Number|Issue Time):.*\n?", "", msg, flags=re.IGNORECASE)
            messages.append(msg)
        return "\n\n".join(messages)
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Telemetry disrupted on NOAA SWPC — {e}")
        return ""

def assemble_news_delta() -> str:
    """Gathers and formats active news inputs for synthesis."""
    news_items = []
    for name, url in FEEDS.items():
        news_items.extend(fetch_rss_feed(name, url))
        
    noaa = fetch_noaa_alerts()
    
    summary_parts = []
    if news_items:
        summary_parts.append("=== CAPTURED TELEMETERED NEWS ===")
        for i, item in enumerate(news_items, 1):
            desc_str = f" - {item['description']}" if item['description'] else ""
            summary_parts.append(f"[{item['source']}]: {item['title']}{desc_str}")
            
    if noaa:
        summary_parts.append("\n=== NOAA SWPC SPACE WEATHER HIGHLIGHTS ===")
        # Filter out comments/empty lines
        noaa_lines = [line.strip() for line in noaa.splitlines() if line.strip() and not line.strip().startswith("#")]
        summary_parts.extend(noaa_lines[:15])
        
    return "\n".join(summary_parts)

def generate_lore_prompt(news_summary: str) -> str:
    """Builds system prompt for Gemini lore synthesis."""
    return f"""You are the central Narrative Synthesis Core for the "Loom" of Chaya Berry Goose (CBG Studio), an Industrial Noir/Tech-Wear brand.

The current world-state delta has captured the following raw signals of real-world chaos, infrastructure failures, server outages, space weather, cybersecurity incidents, and technological friction:

\"\"\"
{news_summary}
\"\"\"

Your task: Synthesize these real-world disruptions of the past hour into a single, cohesive, high-fidelity textile lore "Incident" or "World-State Delta".

This must be translated through the trademark CBG clinical, Brutalist, and Industrial Noir perspective. Do not use generic corporate language, hype, or marketing speak. Use clinical, technical, and atmospheric vocabulary (e.g. "Abyssal", "flux", "rift", "interference", "decay", "breach", "resonance", "overload", "scour").

First, generate a unique, evocative, and dark TWO-WORD Industrial Noir title of the incident/pattern (examples: "Signal Scour", "Silicon Pulse", "Cobalt Surge", "Thermal Breach", "Voltage Fracture").

Output the synthesized result ONLY in this exact Markdown schema:

# [Two-Word Title]

## Description
(2-3 sentences. A technical, clinical narrative block describing the world-state incident and how it has infiltrated the active simulation of the Loom. Highlight how infrastructure or natural forces interacted.)

## Palette
(4-6 colors representing the aesthetic palette of this event, formatted exactly as "Name (#HEXCODE)" entries on separate lines with a leading dash, e.g., "- Cyan Surge (#00FFF0)")

## Motifs
(4-6 visual pattern keywords, comma-separated, e.g., grid patterns, interference fringes, signal noise, liquid cooling lines)

## Prompt Modifiers
(Comma-separated textile/design modifiers suitable for clothing generation, e.g., brutalist concrete texture, distorted signal lines, retro-reflective markings, digital noise map)

Rules:
- Section headers must be exactly: ## Description, ## Palette, ## Motifs, ## Prompt Modifiers
- No extra sections, no HTML, no introductory or explanatory text, no markdown backticks enclosing the entire response.
- Output the raw markdown document and nothing else.
"""

def save_lore_file(generated_text: str) -> tuple[str, Path]:
    """Parse title from generated markdown and write to files under artifacts/lore/."""
    title = None
    for line in generated_text.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break
            
    if not title:
        title = "Neural Friction"
        
    sanitized_title = re.sub(r'[^\w\s-]', '', title).strip()
    
    output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "lore"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / f"{sanitized_title}.md"
    counter = 2
    while filepath.exists():
        filepath = output_dir / f"{sanitized_title} {counter}.md"
        counter += 1
        
    filepath.write_text(generated_text, encoding="utf-8")
    print(f"[SYSTEM_SUCCESS]: New active simulation lore written → {filepath}")
    return title, filepath

def run_lore_generation() -> tuple[str, Path]:
    """Retrieves news feeds and generates brand new Industrial Noir lore from it."""
    news_summary = assemble_news_delta()
    if not news_summary.strip():
        # Safeguard fallback if all network feeds somehow failed
        news_summary = "[Telemetry Loss]: Solar flares detected. Grid fluctuations observe in region 0."
        
    # Hook into Gemini via the existing skill uplink
    model = initialize_loom_uplink()
    prompt = generate_lore_prompt(news_summary)
    
    print("[SYSTEM_LOG]: Engaging news-driven synthesis via the Loom Uplink …")
    specimen_data = generate_specimen_data(model, prompt)
    
    # Save the output file
    title, path = save_lore_file(specimen_data)
    return title, path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBG News-driven Lore Generator (Hourly Cadence)")
    args = parser.parse_args()
    
    title, path = run_lore_generation()
    print(f"[SYSTEM_LOG]: Final generated theme name → {title}")
