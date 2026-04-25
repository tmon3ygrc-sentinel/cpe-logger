import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# Try using DATABASE_ID instead of DS_ID
CMMC_DB_ID = os.getenv("CMMC_DATABASE_ID") or "32a55ed7403880b396e0de9386a76ff7"

notion = Client(auth=os.getenv("NOTION_TOKEN"))

CONTROLS_TO_SEED = [
    {"control_id": "AC.L2-3.1.1", "name": "Account Management", "framework": "CMMC 2.0 L2"},
    {"control_id": "IA.L2-3.5.3", "name": "Multi-factor Authentication", "framework": "CMMC 2.0 L2"},
    {"control_id": "SI.L2-3.14.2", "name": "Malicious Code Protection", "framework": "CMMC 2.0 L2"},
    {"control_id": "SI.L2-3.14.1", "name": "System Monitoring", "framework": "CMMC 2.0 L2"},
    {"control_id": "AT.L2-3.2.1", "name": "Security Awareness Training", "framework": "CMMC 2.0 L2"},
    {"control_id": "CM.L2-3.4.1", "name": "Configuration Management", "framework": "CMMC 2.0 L2"},
]

def seed_controls():
    print(f"🚀 Seeding {len(CONTROLS_TO_SEED)} CMMC stubs using database_id...\n")
    for ctrl in CONTROLS_TO_SEED:
        try:
            notion.pages.create(
                parent={"database_id": CMMC_DB_ID},   # Changed to database_id
                properties={
                    "Name": {"title": [{"type": "text", "text": {"content": ctrl["control_id"]}}]},
                    "Control Name": {"rich_text": [{"type": "text", "text": {"content": ctrl["name"]}}]},
                    "Framework": {"select": {"name": ctrl["framework"]}},
                    "Gap Status": {"select": {"name": "Not Started"}},
                }
            )
            print(f"✅ Seeded: {ctrl['control_id']} → {ctrl['name']}")
        except Exception as e:
            print(f"❌ Failed {ctrl['control_id']}: {e}")

if __name__ == "__main__":
    seed_controls()
    print("\n✅ Run complete.")