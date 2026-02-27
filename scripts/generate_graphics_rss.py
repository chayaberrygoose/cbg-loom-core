#!/usr/bin/env python3
# [FILE_ID]: generate_graphics_rss.py // VERSION: 1.2 // STATUS: STABLE 
import os
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

# [CONFIG]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
GRAPHICS_DIR = os.path.join(REPO_ROOT, "artifacts", "graphics")
OUTPUT_DIR = os.path.join(REPO_ROOT, "artifacts", "feeds")
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/chayaberrygoose/cbg-loom-core/main"
GITHUB_REPO_URL = "https://github.com/chayaberrygoose/cbg-loom-core"

def create_rss_feed(category_name, items):
    """Generates an RSS 2.0 feed for a specific graphics category."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    ET.SubElement(channel, "title").text = f"CBG Studio // {category_name.upper()} // DATA_STREAM"
    ET.SubElement(channel, "link").text = f"{GITHUB_REPO_URL}/tree/main/artifacts/graphics/{category_name}"
    ET.SubElement(channel, "description").text = f"High-fidelity {category_name} specimens from the Chaya Berry Goose Loom."
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    for item in items:
        rss_item = ET.SubElement(channel, "item")
        ET.SubElement(rss_item, "title").text = item['title']
        ET.SubElement(rss_item, "link").text = item['link']
        ET.SubElement(rss_item, "guid", isPermaLink="false").text = item['guid']
        ET.SubElement(rss_item, "pubDate").text = item['pubDate']
        
        description = ET.SubElement(rss_item, "description")
        description.text = f'<img src="{item["image_url"]}" /><br/>Prompt: {item["prompt"]}'

    xml_str = ET.tostring(rss, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
    return pretty_xml

def scan_graphics():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    categories = ["mockups", "tiles", "textures", "standalone", "logos"]
    
    for cat in categories:
        cat_path = os.path.join(GRAPHICS_DIR, cat)
        if not os.path.exists(cat_path):
            print(f"// WARNING: Category path {cat_path} does not exist.")
            continue
            
        feed_items = []
        for root, dirs, files in os.walk(cat_path):
            images = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
            if not images:
                continue
                
            prompt_text = "No prompt available."
            if "prompt.txt" in files:
                try:
                    with open(os.path.join(root, "prompt.txt"), "r") as f:
                        prompt_text = f.read().strip()
                except Exception:
                    pass
            
            folder_name = os.path.basename(root)
            if folder_name == cat:
                continue

            pub_date_raw = None
            try:
                date_str = folder_name.split("__")[0]
                pub_date_raw = datetime.datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            except Exception:
                pub_date_raw = datetime.datetime.now()

            for img in images:
                rel_path = os.path.relpath(os.path.join(root, img), REPO_ROOT)
                image_url = f"{GITHUB_RAW_BASE}/{rel_path}"
                
                feed_items.append({
                    "title": folder_name.replace("__", " // ").replace("-", " "),
                    "link": f"{GITHUB_REPO_URL}/blob/main/{rel_path}",
                    "guid": rel_path,
                    "pubDate": pub_date_raw,
                    "image_url": image_url,
                    "prompt": prompt_text
                })

        if feed_items:
            feed_items.sort(key=lambda x: x["pubDate"], reverse=True)
            
            for item in feed_items:
                item["pubDate"] = item["pubDate"].strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            rss_content = create_rss_feed(cat, feed_items)
            output_file = os.path.join(OUTPUT_DIR, f"{cat}.xml")
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(rss_content)
            print(f"// SIGNAL_RECOVERY: Generated {cat}.xml feed at {output_file}")

if __name__ == "__main__":
    scan_graphics()
