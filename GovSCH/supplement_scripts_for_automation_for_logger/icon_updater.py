import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = "32a55ed7403880b396e0de9386a76ff7"

DOMAIN_ICONS = {
    "Access Control (AC)": "🔑",
    "Identification (IA)": "🆔",
    "System & Communications (SC)": "🌐",
    "System Integrity (SI)": "💉",
    "Audit (AU)": "📜",
    "Risk Assessment (RA)": "🎯",
    "Personnel Security (PS)": "👤",
    "Physical Protection (PE)": "🏢",
    "Incident Response (IR)": "🚨",
    "Configuration Management (CM)": "⚙️",
    "Maintenance (MA)": "🔧",
    "Media Protection (MP)": "💾",
    "Awareness (AT)": "🧠",
    "Security Assessment (CA)": "🩺",
    "Recovery (RE)": "⏪",
    "Supply Chain Risk Management (SR)": "⛓️",
    "System & Services Acquisition (SA)": "🛒"
}

def update_cmmc_icons():
    print("🚀 Starting Tier 1 Icon Update...")
    has_more = True
    start_cursor = None
    count = 0

    while has_more:
        query_params = {"database_id": DATABASE_ID}
        if start_cursor:
            query_params["start_cursor"] = start_cursor
        
        response = notion.databases.query(**query_params)
        
        for page in response["results"]:
            page_id = page["id"]
            domain_prop = page["properties"].get("Domain", {}).get("select")
            
            if domain_prop:
                domain_name = domain_prop["name"]
                icon_emoji = DOMAIN_ICONS.get(domain_name)
                
                if icon_emoji:
                    try:
                        notion.pages.update(
                            page_id=page_id,
                            icon={"type": "emoji", "emoji": icon_emoji}
                        )
                        print(f"✅ Updated: {domain_name} -> {icon_emoji}")
                        count += 1
                    except Exception as e:
                        print(f"❌ Failed to update {page_id}: {e}")

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    print(f"\n✅ Mission Complete. {count} icons applied.")

if __name__ == "__main__":
    update_cmmc_icons()
