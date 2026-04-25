import os
from notion_client import Client
from dotenv import load_dotenv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("DATABASE_ID")

result = notion.databases.retrieve(database_id=DATABASE_ID)

print("\n=== EXACT PROPERTY NAMES ===")
for name, prop in result["properties"].items():
    print(f"{repr(name)} → type: {prop['type']}")
