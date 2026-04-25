import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from notion_client import Client
from dotenv import load_dotenv

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.absolute()
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
DATABASE_ID    = os.getenv("DATABASE_ID")
CMMC_DB_ID     = os.getenv("CMMC_DATABASE_ID", "32a55ed7403880b396e0de9386a76ff7")
DEBUG_MODE     = os.getenv("DEBUG", "0") == "1"
INPUT_FILE     = SCRIPT_DIR / "governance_input.txt"

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("❌ NOTION_TOKEN or DATABASE_ID missing from .env")

notion = Client(auth=NOTION_TOKEN)

# ─── TAXONOMY ENFORCEMENT (V4.27 Logic) ───────────────────────────────────────

# These dictionaries allow for fuzzy matching. The KEY is what goes to Notion.
# The LIST contains common AI "drifts" to catch and normalize.
TAXONOMY_MAPS = {
    "threat_actor": {
        "e-crime": ["cybercrime", "financially motivated", "fraud group", "scammers", "criminal"],
        "nation-state": ["apt", "state-sponsored", "china", "russia", "iran", "north korea"],
        "insider": ["employee", "contractor", "internal"],
        "hacktivist": ["activist", "hacktivism"],
        "unknown": ["none", "unattributed"]
    },
    "target_sector": {
        "finance": ["bank", "fintech", "financial"],
        "healthcare": ["hospital", "medical"],
        "government": ["federal", "state", "municipal"],
        "defense": ["dod", "military"],
        "technology": ["tech", "saas", "cloud"],
        "consumer": ["retail", "end-user"],
        "corporate-enterprise": ["enterprise", "business"],
        "unknown": ["none"]
    },
    "impacted_identity_provider": {
        "entra-id": ["azure ad", "entra", "microsoft identity", "m365"],
        "okta": [],
        "google-workspace": ["gmail", "google"],
        "on-prem-ad": ["active directory"],
        "oauth": [],
        "none": ["unknown"]
    }
}

def normalize_value(field_name: str, value: str) -> str:
    """Forces AI output into allowed Notion Enums."""
    val = value.strip().lower()
    if field_name not in TAXONOMY_MAPS:
        return value # No mapping for this field, return as is

    mapping = TAXONOMY_MAPS[field_name]
    for canonical, aliases in mapping.items():
        if val == canonical or val in aliases:
            return canonical
        # Fuzzy check: does the alias exist inside the string?
        for alias in aliases:
            if alias in val:
                return canonical
    
    return "unknown"

# ─── CMMC LOOKUP ──────────────────────────────────────────────────────────────

CMMC_CACHE: Dict[str, str] = {}

def load_cmmc_cache():
    """Load all CMMC control IDs → Notion page IDs into memory."""
    if CMMC_CACHE: return # Skip if already loaded
    print("📡 Loading CMMC framework...")
    try:
        has_more = True
        cursor = None
        while has_more:
            params = {"database_id": CMMC_DB_ID}
            if cursor:
                params["start_cursor"] = cursor
            res = notion.databases.query(**params)
            for page in res["results"]:
                title_prop = page["properties"].get("Name", {}).get("title", [])
                if title_prop:
                    control_id = title_prop[0]["plain_text"].strip()
                    CMMC_CACHE[control_id] = page["id"]
            has_more = res.get("has_more", False)
            cursor = res.get("next_cursor")
        print(f"✅ CMMC cache loaded: {len(CMMC_CACHE)} controls")
    except Exception as e:
        print(f"⚠️  CMMC cache failed: {e} — continuing without relations")

# ─── UTILITIES ────────────────────────────────────────────────────────────────

def to_multi(field_name, val) -> List[dict]:
    """Convert value to Notion multi_select with Taxonomy Enforcement."""
    if not val:
        return []
    
    items = [x.strip() for x in str(val).split(",")]
    normalized_items = []
    
    for i in items:
        if not i or i.lower() in ("unknown", "none", "n/a"):
            continue
        
        # Apply normalization if applicable
        n_val = normalize_value(field_name, i)
        if n_val not in normalized_items:
            normalized_items.append(n_val)

    # Constraint: Max 2 attack tactics to prevent "Tactic Soup"
    if field_name == "attack_tactic":
        normalized_items = normalized_items[:2]

    return [{"name": i} for i in normalized_items]

def to_select(field_name, val) -> Optional[dict]:
    """Convert value to Notion select with Taxonomy Enforcement."""
    if not val or str(val).lower() in ("unknown", "none", ""):
        return {"name": "unknown"}
    
    n_val = normalize_value(field_name, val)
    return {"name": n_val}

def to_number(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

def to_date(val) -> Optional[dict]:
    if not val: return None
    try:
        return {"start": str(val)[:10]}
    except Exception:
        return None

def to_text(val, limit=2000) -> List[dict]:
    if not val: return []
    return [{"text": {"content": str(val)[:limit]}}]

def scrub(text: str) -> str:
    """Strip markdown artifacts and clean up AI formatting."""
    text = re.sub(r'\\([_\[\]=*`#])', r'\1', text)
    text = re.sub(r'^#+\s*(===INTEL_RECORD)', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'```[^\n]*\n?', '', text)
    text = re.sub(r'`', '', text)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    return text

FIELD_FIXES = {
    'intel_datee': 'intel_date',
    'intel_dates': 'intel_date',
    'record_ids': 'record_id',
    'threat_actors': 'threat_actor',
    'attack_technique': 'attack_techniques',
    'control_domain': 'control_domains',
    'cmmc_mappings': 'cmmc_mapping',
    'tag': 'tags',
}

# ─── PARSER ───────────────────────────────────────────────────────────────────

def parse_records() -> List[dict]:
    if not INPUT_FILE.exists():
        print(f"❌ Input file not found: {INPUT_FILE}")
        return []

    content = scrub(INPUT_FILE.read_text(encoding="utf-8"))
    blocks = re.findall(r'===INTEL_RECORD_START===(.*?)===INTEL_RECORD_END===', content, re.DOTALL)

    if not blocks:
        print("⚠️  No intel records found.")
        return []

    print(f"\n📊 Found {len(blocks)} record(s)...")
    records = []
    for idx, block in enumerate(blocks, 1):
        raw = {}
        for line in block.strip().split('\n'):
            line = line.strip()
            if '::' not in line: continue
            parts = line.split('::', 1)
            key = FIELD_FIXES.get(parts[0].strip(), parts[0].strip())
            val = parts[1].strip()
            if val and val.lower() not in ("", "n/a"):
                raw[key] = val

        if raw.get('record_id'):
            records.append(raw)
    return records

# ─── NOTION PUSH ──────────────────────────────────────────────────────────────

MULTI_SELECT = {
    "tags", "control_domains", "intel_category", "kill_chain_phase",
    "attack_tactic", "attack_techniques", "threat_actor", "target_sector",
    "priority_level", "detection_opportunities", "identity_impact",
    "impacted_identity_provider", "content_type"
}

SELECT = {
    "source", "cisa_kev", "active_exploitation", "exploit_maturity",
    "intel_type", "asset_criticality", "response_urgency", "story_type",
    "confidence", "cpe_category"
}

DATE_FIELDS = {"intel_date", "intel_timestamp", "date_detected"}
SKIP = {"record_id", "url", "title", "date_watched", "cpe_credits", "cmmc_mapping"}

def push_record(record: dict, base_title: str, url: str) -> bool:
    record_id = record.get("record_id", "unknown")
    
    # Extract specific title if provided in the record, else use base_title
    raw_title = record.get("title", base_title)
    page_title = f"{raw_title} [{record_id}]"

    props = {
        "title": {"title": to_text(page_title)},
        "url": {"url": url},
        "date_watched": {"date": {"start": date.today().isoformat()}},
        "cpe_credits": {"number": to_number(record.get("cpe_credits")) or 0.05},
        "record_id": {"rich_text": to_text(record_id)},
    }

    # Process all fields through the taxonomy filter
    for key, val in record.items():
        if key in SKIP or key in props or not val: continue

        if key in MULTI_SELECT:
            result = to_multi(key, val)
            if result: props[key] = {"multi_select": result}

        elif key in SELECT:
            result = to_select(key, val)
            if result: props[key] = {"select": result}

        elif key in DATE_FIELDS:
            result = to_date(val)
            if result: props[key] = {"date": result}

        elif key == "risk_severity_score":
            score = to_number(val)
            if score is not None: props[key] = {"number": score}

        else:
            props[key] = {"rich_text": to_text(val)}

    # CMMC Relation Logic
    cmmc_raw = record.get("cmmc_mapping", "")
    if cmmc_raw:
        control_ids = [x.strip() for x in cmmc_raw.split(",") if x.strip()]
        relations = [{"id": CMMC_CACHE[cid]} for cid in control_ids if cid in CMMC_CACHE]
        if relations:
            props["Master Frameworks(CMMC 2.0 / NIST 800-171)"] = {"relation": relations}

    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=props)
        print(f"✅ Logged: {record_id}")
        return True
    except Exception as e:
        print(f"❌ Failed: {record_id} | {e}")
        return False

# ─── MISSION CONTROL ──────────────────────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("🛡️  STAR CPE LOGGER V5.1 — TAXONOMY ENFORCED")
    print("="*55)

    while True:
        print("\n1. Log Daily Threat Brief\n2. Exit")
        choice = input("\nSelection: ").strip()

        if choice == "2": break
        if choice == "1":
            url = input("Source URL: ").strip()
            base_title = input("Base Title (Optional): ").strip()
            if not base_title: base_title = f"Simply Cyber {date.today().strftime('%m/%d')}"

            load_cmmc_cache()
            records = parse_records()

            if not records:
                print("⚠️  No valid records found in governance_input.txt")
                continue

            print(f"\n🚀 Processing {len(records)} records through taxonomy filter...")
            success = sum(push_record(r, base_title, url) for r in records)
            print(f"\n📊 SUMMARY: {success}/{len(records)} logged successfully")

if __name__ == "__main__":
    main()