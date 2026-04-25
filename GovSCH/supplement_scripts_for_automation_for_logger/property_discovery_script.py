import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()
notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("DATABASE_ID")

def discover_properties():
    print(f"🔍 Accessing Database: {DATABASE_ID}")
    try:
        db = notion.databases.retrieve(database_id=DATABASE_ID)
        print("\n✅ CONNECTION SUCCESSFUL. Properties found:")
        print("-" * 50)
        for name, data in db["properties"].items():
            # ! = Special focus for your current bugs
            focus = " <--- Check this!" if "Framework" in name or "identity" in name.lower() else ""
            print(f"Name: '{name}' | Type: {data['type']}{focus}")
        print("-" * 50)
        print("\n💡 ACTION: Copy the exact text between the single quotes '' for")
        print("   'Master Frameworks' and 'impacted_identity_provider' into your v4.18.2 script.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    discover_properties()