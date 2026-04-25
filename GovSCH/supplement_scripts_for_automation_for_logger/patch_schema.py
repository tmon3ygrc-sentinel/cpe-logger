import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# Using the raw ID as discovered
DATABASE_ID = "33855ed7403880f6a615000b4bf49a40" 
notion = Client(auth=os.getenv("NOTION_TOKEN"))

def update_schema():
    print(f"📡 Patching database schema: {DATABASE_ID}...")
    
    # These properties align with your existing 14 CMMC Rev 2 domains
    new_properties = {
        "control_domains": {"multi_select": {}}, # Will hold "SI", "SC", "AC", etc.
        "detection_opportunities": {"rich_text": {}},
        "identity_impact": {"rich_text": {}},
        "attack_techniques": {"multi_select": {}},
        "kill_chain_phase": {"select": {}}
    }

    try:
        notion.databases.update(
            database_id=DATABASE_ID,
            properties=new_properties
        )
        print("✅ Schema updated! Your Strategy DB is now 'Rev 2' compliant.")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    update_schema()