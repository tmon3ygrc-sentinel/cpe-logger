import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

CMMC_DS_ID = "32a55ed7403880b396e0de9386a76ff7"   # Your CMMC data source

notion = Client(auth=os.getenv("NOTION_TOKEN"))

# Your starter controls with Domain (for icon updater)
CONTROLS_TO_SEED = [
    {"control_id": "AC.L2-3.1.1", "name": "Account Management", "framework": "CMMC 2.0 L2", "domain": "Access Control (AC)"},
    {"control_id": "IA.L2-3.5.3", "name": "Multi-factor Authentication", "framework": "CMMC 2.0 L2", "domain": "Identification (IA)"},
    {"control_id": "SI.L2-3.14.2", "name": "Malicious Code Protection", "framework": "CMMC 2.0 L2", "domain": "System Integrity (SI)"},
    {"control_id": "SI.L2-3.14.1", "name": "System Monitoring", "framework": "CMMC 2.0 L2", "domain": "System Integrity (SI)"},
    {"control_id": "AT.L2-3.2.1", "name": "Security Awareness Training", "framework": "CMMC 2.0 L2", "domain": "Awareness and Training (AT)"},
    {"control_id": "CM.L2-3.4.1", "name": "Configuration Management", "framework": "CMMC 2.0 L2", "domain": "Configuration Management (CM)"},
]

def check_existing_controls():
    print("🔍 Checking existing controls in CMMC database...\n")
    try:
        res = notion.request(
            path=f"data_sources/{CMMC_DS_ID}/query",
            method="POST",
            body={"page_size": 100}
        )
        existing = {}
        for page in res.get("results", []):
            title_list = page.get("properties", {}).get("Name", {}).get("title", [])
            if title_list:
                cid = title_list[0].get("plain_text", "").strip()
                if cid:
                    existing[cid] = page["id"]
        print(f"✅ Found {len(existing)} existing controls.")
        return existing
    except Exception as e:
        print(f"⚠️ Could not query existing controls: {e}")
        return {}

def seed_new_controls(existing):
    print(f"\n🚀 Seeding new controls (skipping duplicates)...\n")
    added = 0
    for ctrl in CONTROLS_TO_SEED:
        if ctrl["control_id"] in existing:
            print(f"⏭️  Skipping (already exists): {ctrl['control_id']}")
            continue

        try:
            notion.pages.create(
                parent={"type": "data_source_id", "data_source_id": CMMC_DS_ID},
                properties={
                    "Name": {"title": [{"type": "text", "text": {"content": ctrl["control_id"]}}]},
                    "Control Name": {"rich_text": [{"type": "text", "text": {"content": ctrl["name"]}}]},
                    "Framework": {"select": {"name": ctrl["framework"]}},
                    "Domain": {"select": {"name": ctrl["domain"]}},           # ← For your icon_updater
                    "Gap Status": {"select": {"name": "Not Started"}},
                }
            )
            print(f"✅ Seeded new: {ctrl['control_id']} → {ctrl['name']}")
            added += 1
        except Exception as e:
            print(f"❌ Failed {ctrl['control_id']}: {e}")

    print(f"\n✅ Seeding complete. Added {added} new controls.")

if __name__ == "__main__":
    existing = check_existing_controls()
    seed_new_controls(existing)