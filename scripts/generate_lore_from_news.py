#!/usr/bin/env python3
# /* [FILE_ID]: scripts/GENERATE_LORE_FROM_NEWS // VERSION: 1.1 // STATUS: STABLE */
# [NARRATIVE]: Scrapes stable real-time news and space weather feeds looking back 24 hours,
#              then uses Gemini to synthesize active simulation lore (Incident Brief / World-State Delta)
#              with multiple distinct themes and concrete physical motifs directly inside the artifacts/lore/ directory.
# [USAGE]: python3 scripts/generate_lore_from_news.py

import os
import sys
import re
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import datetime
from datetime import datetime, timedelta, timezone
import html
from email.utils import parsedate_to_datetime

import requests

# Ensure project root is in the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.skills.gemini_skill.gemini_skill import initialize_loom_uplink, generate_specimen_data

# ─── NEWS FEEDS CONFIGURATION ─────────────────────────────────
FEEDS = {
    "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Hacker News": "https://news.ycombinator.com/rss",
    "NASA Breaking News": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "Slashdot": "http://rss.slashdot.org/Slashdot/slashdotMain",
    "Wired": "https://www.wired.com/feed/rss",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "Phys.org": "https://phys.org/rss-feed/"
}

NOAA_ALERTS_URL = "https://services.swpc.noaa.gov/products/alerts.json"

def fetch_rss_feed(name: str, url: str, max_items: int = 15, hours_lookback: int = 1) -> list:
    """Fetch and parse RSS feed, return list of {title, description, source, pub_date, link}
    filtering for items within the lookback window. Falls back to at least top 5 items."""
    print(f"[SYSTEM_LOG]: Ingesting feed signals from: {name} (1h filter active) …")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 CBGStudio-Loom/2.0"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        
        # Clean response text from potential weird characters/bytes
        root = ET.fromstring(resp.content)
        all_items = root.findall(".//item")
        
        filtered_items = []
        now = datetime.now(timezone.utc)
        
        for item in all_items:
            title_el = item.find("title")
            desc_el = item.find("description")
            pub_date_el = item.find("pubDate")
            link_el = item.find("link")
            
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
            pub_date_str = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            
            # Clean HTML tags and entities
            title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
            desc = re.sub(r"<[^>]+>", "", html.unescape(desc)).strip()
            
            if not title:
                continue
                
            # Filter by hours_lookback
            is_recent = True
            if pub_date_str:
                try:
                    dt = parsedate_to_datetime(pub_date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if (now - dt) > timedelta(hours=hours_lookback):
                        is_recent = False
                except Exception:
                    pass
            
            if is_recent:
                filtered_items.append({
                    "title": title,
                    "description": desc,
                    "source": name,
                    "pub_date": pub_date_str,
                    "link": link
                })
                if len(filtered_items) >= max_items:
                    break
                    
        # Robust fallback: if fewer than 5 items found in last hour, take the top 5 from the feed anyway
        if len(filtered_items) < 5 and len(all_items) > 0:
            for item in all_items:
                title_el = item.find("title")
                desc_el = item.find("description")
                pub_date_el = item.find("pubDate")
                link_el = item.find("link")
                
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                pub_date_str = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                
                title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
                desc = re.sub(r"<[^>]+>", "", html.unescape(desc)).strip()
                
                if not title:
                    continue
                    
                # Check if it's already added to avoid duplicates
                if any(x["title"] == title for x in filtered_items):
                    continue
                    
                filtered_items.append({
                    "title": title,
                    "description": desc,
                    "source": name,
                    "pub_date": pub_date_str,
                    "link": link
                })
                if len(filtered_items) >= 5:
                    break
                    
        return filtered_items
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Feed disruption on {name} — {e}")
        return []

def fetch_noaa_alerts(hours_lookback: int = 1) -> str:
    """Fetch space weather alerts from NOAA SWPC (JSON format) within last hour."""
    print("[SYSTEM_LOG]: Ingesting NOAA Space Weather telemetry (1h filter active) …")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 CBGStudio-Loom/2.0"}
        resp = requests.get(NOAA_ALERTS_URL, headers=headers, timeout=12)
        resp.raise_for_status()
        alerts = resp.json()
        messages = []
        now = datetime.now(timezone.utc)
        
        for alert in alerts:
            issue_dt_str = alert.get("issue_datetime", "").strip()
            is_recent = True
            if issue_dt_str:
                try:
                    dt = datetime.fromisoformat(issue_dt_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if (now - dt) > timedelta(hours=hours_lookback):
                        is_recent = False
                except Exception:
                    try:
                        dt = datetime.strptime(issue_dt_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                        dt = dt.replace(tzinfo=timezone.utc)
                        if (now - dt) > timedelta(hours=hours_lookback):
                            is_recent = False
                    except Exception:
                        pass
            
            if is_recent:
                msg = alert.get("message", "").strip()
                # Clean repetitive/technical metadata to keep lore focused
                msg = re.sub(r"(Space Weather Message Code|Serial Number|Issue Time):.*\n?", "", msg, flags=re.IGNORECASE)
                messages.append(msg)
                if len(messages) >= 8:
                    break
                    
        # Robust fallback: fetch first 4 available if none are in last hour
        if not messages and alerts:
            for alert in alerts[:4]:
                msg = alert.get("message", "").strip()
                msg = re.sub(r"(Space Weather Message Code|Serial Number|Issue Time):.*\n?", "", msg, flags=re.IGNORECASE)
                messages.append(msg)
                
        return "\n\n".join(messages)
    except Exception as e:
        print(f"[SYSTEM_WARNING]: Telemetry disrupted on NOAA SWPC — {e}")
        return ""

def assemble_news_delta() -> str:
    """Gathers and formats active news inputs for synthesis."""
    import random
    news_items = []
    # Cap each feed to max 4 items to enforce balance/variety between sources
    for name, url in FEEDS.items():
        news_items.extend(fetch_rss_feed(name, url, max_items=4, hours_lookback=1))
        
    noaa = fetch_noaa_alerts(hours_lookback=1)
    
    # Shuffle news items to prevent any single dominant source (like BBC General News)
    # from clustering together and biasing the narrative synthesis.
    random.shuffle(news_items)
    
    summary_parts = []
    if news_items:
        summary_parts.append("=== CAPTURED TELEMETERED NEWS (1-HOUR REAL-TIME DELTA) ===")
        for i, item in enumerate(news_items, 1):
            desc_str = f" - {item['description']}" if item['description'] else ""
            link_str = f" (Source Link: {item['link']})" if item.get('link') else ""
            summary_parts.append(f"[{item['source']}]: {item['title']}{desc_str}{link_str}")
            
    if noaa:
        summary_parts.append("\n=== NOAA SWPC SPACE WEATHER HIGHLIGHTS ===")
        # Filter out comments/empty lines
        noaa_lines = [line.strip() for line in noaa.splitlines() if line.strip() and not line.strip().startswith("#")]
        summary_parts.extend(noaa_lines[:15])
        
    return "\n".join(summary_parts)

def generate_lore_prompt(news_summary: str) -> str:
    """Builds system prompt for Gemini lore synthesis, forcing multi-article, topical concrete detail."""
    return f"""You are the central Narrative Synthesis Core for the "Loom" of Chaya Berry Goose (CBG Studio), an Industrial Noir/Tech-Wear brand.

The current 1-hour world-state delta has captured the following raw signals of real-world chaos, infrastructure failures, server outages, space weather, cybersecurity incidents, and technological friction:

\"\"\"
{news_summary}
\"\"\"

Your task: Analyze these real-world disruptions of the past hour. Identify between 5 to 10 completely distinct real-world incidents, topics, technological failures, space anomalies, or research breakthroughs from the provided telemetry.
Then, synthesize these distinct events into a single, cohesive, high-fidelity textile lore "Incident" or "World-State Delta" for CBG Studio.

This must be translated through the trademark CBG clinical, Brutalist, and Industrial Noir perspective. Do not use generic corporate language, hype, or marketing speak. Use clinical, technical, and atmospheric vocabulary (e.g. "Abyssal", "flux", "rift", "interference", "decay", "breach", "resonance", "overload", "scour").

First, generate a unique, evocative, and dark TWO-WORD Industrial Noir title of the collective incident/pattern (examples: "Signal Scour", "Silicon Pulse", "Cobalt Surge", "Thermal Breach", "Voltage Fracture").

Output the synthesized result ONLY in this exact Markdown schema:

# [Two-Word Title]

## Description
(A highly detailed technical, clinical narrative block. Do NOT make this abstract or generic. You must explicitly name, describe, and synthesize the 5 to 10 distinct real-world incidents you identified from the news summaries. Mention specific details, organizations, locations, or technical terms directly from those 5 to 10 incidents. Explain how these diverse signals collided in the Loom, causing a collective material shift or simulation anomaly.)

## Palette
(5-8 colors representing the aesthetic palette of these combined events, formatted exactly as "Color Name (#HEXCODE)" entries on separate lines with a leading dash. The color names themselves must be inspired by the specific incidents, e.g. "- Outage Amber (#FF7A00)" or "- Auroral Oxide (#1F302B)".)

## Motifs
(6-10 visual pattern keywords, comma-separated. CRITICAL: Strictly avoid abstract, generic geometrical phrases like 'grid patterns', 'thermal lines', 'glitch lines', or 'noise'. Instead, provide highly specific, concrete physical and technical visual elements directly derived from the 5 to 10 real-world incidents, e.g. 'undersea coaxial cable cross-sections', 'aviation flight instrument HUD vectors', 'mainframe rack-mount ventilation slot arrays', 'orbital satellite telemetric coordinate lines', or 'coronal emission spectrogram paths'.)

## Prompt Modifiers
(6-10 comma-separated textile/design modifiers suitable for Midjourney/Gemini clothing and pattern generation. CRITICAL: Avoid abstract concepts. Specify physical, tangible textures, wireframes, technical drawings, blueprints, or authentic telemetry layouts related specifically to the events, e.g. 'brutalist cast concrete slab texture', 'etched copper circuit tracing lanes', 'translucent heavy-duty ripstop casing', 'vintage flight log vector diagrams'.)

## Source Links
(Provide a neat checklist of markdown links to the specific source links/websites for the 5 to 10 real-world incidents identified from the telemetry signal feeds, e.g., "- Slashdot: [Title of article](URL)" or "- BBC: [Title of article](URL)". DO NOT MAKE UP LINKS; ONLY use real links explicitly provided in the news feeds or telemetry summaries. If a telemetry feed like NOAA doesn't have a specific link, link to the parent service URL, e.g., 'https://services.swpc.noaa.gov/'.)

Rules:
- Section headers must be exactly: ## Description, ## Palette, ## Motifs, ## Prompt Modifiers, ## Source Links
- No extra sections, no HTML, no introductory or explanatory text, no markdown backticks enclosing the entire response.
- Output the raw markdown document and nothing else.
"""

def save_lore_file(generated_text: str) -> tuple[str, Path]:
    """Saves the news-generated markdown as Active Simulation.md, overwriting previous run to prevent duplicate pollution."""
    title = None
    for line in generated_text.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break
            
    if not title:
        title = "Neural Friction"
        
    output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "lore"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / "Active Simulation.md"
    filepath.write_text(generated_text, encoding="utf-8")
    print(f"[SYSTEM_SUCCESS]: Active simulation lore successfully written/overwritten → {filepath}")
    return "Active Simulation", filepath

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
