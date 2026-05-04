import os
from dotenv import load_dotenv
from notion_client import Client
from datetime import datetime

load_dotenv()
notion = Client(auth=os.getenv('NOTION_TOKEN'))

# Main STAR data source (the one that works)
DS_ID = "33855ed7-4038-80f6-a615-000b4bf49a40"

def ingest_threat(item):
    properties = {
        "Topic/Concept": {"title": [{"type": "text", "text": {"content": item["title"]}}]},
        "Strategic Pillar": {"multi_select": [{"name": p} for p in item.get("pillars", ["Supply Chain"])]},
        "vCISO Hot Take": {"rich_text": [{"type": "text", "text": {"content": item.get("hot_take", "")}}]},
        "Source URL": {"url": item.get("url") or None},
        "Maturity Target": {"select": {"name": item.get("maturity", "L3 - Repeatable/Managed")}},
        "Horizon": {"select": {"name": item.get("horizon", "Immediate")}},
        "Domain": {"select": {"name": item.get("domain", "Supply Chain")}}   # for your icon updater
    }

    try:
        page = notion.pages.create(
            parent={"type": "data_source_id", "data_source_id": DS_ID},
            properties=properties
        )
        print(f"✅ Ingested: {item['title']}")
    except Exception as e:
        print(f"❌ Failed: {item['title']} | {e}")

# Example items - add more as needed
items = [
    {
        "title": "Linux Local Privilege Escalation (LPE) - April 20",
        "pillars": ["System and Information Integrity", "Vulnerability Management"],
        "hot_take": "Routine patch cycle update for Linux kernel vulnerabilities. Requires local access for exploitation.",
        "url": "youtube.com/liv...EtcfDd",
        "maturity": "L3 - Repeatable/Managed",
        "horizon": "Immediate",
        "domain": "System and Information Integrity"
    }
]

if __name__ == "__main__":
    for item in items:
        ingest_threat(item)