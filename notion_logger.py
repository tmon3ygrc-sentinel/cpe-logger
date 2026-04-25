"""
🛡️ STAR CPE LOGGER V5.3 — PROJECT DARKSWORD
Integrated for CMMC 2.0 & NIST 800-171
Schema-verified. Hashtag-stripped. Defaults applied.
"""

import os
import re
from datetime import date
from pathlib import Path
from typing import List, Dict
from notion_client import Client
from dotenv import load_dotenv

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.absolute()
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID  = os.getenv("DATABASE_ID")
CMMC_DB_ID   = os.getenv("CMMC_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("❌ NOTION_TOKEN or DATABASE_ID missing from .env")

# ─── SCHEMA (verified against live Notion database) ───────────────────────────

FIELD_FIXES = {
    "impacted_identity":   "impacted_identity_provider",
    "impacted_identitty":  "impacted_identity_provider",
    "exploit_maturity":    "exploit_maturity",
    "executive_summary":   "executive_summary",
    "cmmc_mappings":       "cmmc_mapping",
    "tag":                 "tags",
    "intel_datee":         "intel_date",
    "kill_chaiin_phase":   "kill_chain_phase",
}

SELECT = {
    "content_category",
    "exploit_maturity",
    "source",
    "story_type",
    "response_urgency",
    "asset_criticality",
    "cpe_category",
    "active_exploitation",
    "confidence",
    "cisa_kev",
    "intel_type",
}

MULTI_SELECT = {
    "detection_opportunities",
    "attack_tactic",
    "identity_impact",
    "dfir_phase",
    "content_type",
    "tags",
    "kill_chain_phase",
    "impacted_identity_provider",
    "attack_techniques",
    "target_sector",
    "threat_actor",
    "investigation_type",
    "priority_level",
    "intel_category",
    "control_domains",
}

DATE_FIELDS = {
    "intel_date",
    "intel_timestamp",
}

RICH_TEXT_FIELDS = {
    "key_takeaways",
    "executive_summary",
    "operational_relevance",
}

SKIP = {
    "record_id",
    "url",
    "title",
    "date_watched",
    "cpe_credits",
    "cmmc_mapping",
}

# ─── UTILITIES ────────────────────────────────────────────────────────────────

def to_text(val) -> list:
    return [{"text": {"content": str(val)[:2000]}}] if val else []

def to_select(val) -> dict | None:
    return {"name": str(val).strip()} if val else None

def to_multi(val) -> list:
    if isinstance(val, str):
        items = [x.strip().lstrip('#') for x in val.split(",")]
    else:
        items = [str(x).lstrip('#') for x in list(val)]
    return [{"name": i} for i in items if i]

def scrub(text: str) -> str:
    text = re.sub(r'```[^\n]*\n?', '', text)
    text = re.sub(r'[`*]', '', text)
    return text

# ─── CMMC CACHE (paginated) ───────────────────────────────────────────────────

CMMC_CACHE: Dict[str, str] = {}

def load_cmmc_cache():
    if not CMMC_DB_ID:
        return
    print("📡 Loading CMMC framework cache...")
    CMMC_CACHE.clear()
    has_more = True
    next_cursor = None
    page_count = 0

    try:
        while has_more:
            res = notion.databases.query(
                database_id=CMMC_DB_ID,
                start_cursor=next_cursor
            )
            page_count += 1
            for page in res["results"]:
                title_prop = page["properties"].get("Name", {}).get("title", [])
                if title_prop:
                    control_id = title_prop[0]["plain_text"].strip()
                    CMMC_CACHE[control_id] = page["id"]

            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
            print(f"  📄 Page {page_count} loaded — {len(CMMC_CACHE)} controls so far...")

        print(f"✅ CMMC cache fully loaded: {len(CMMC_CACHE)} controls")

    except Exception as e:
        print(f"❌ Failed to load CMMC framework: {e}")

# ─── GRC WRITE-BACK ───────────────────────────────────────────────────────────

def update_compliance_status(control_ids: List[str], log_page_url: str):
    """Updates the Master Frameworks database to link evidence and flag status."""
    for cid in control_ids:
        # Check if the Control ID exists in the cache we just loaded
        if cid in CMMC_CACHE:
            page_id = CMMC_CACHE[cid]
            try:
                # This reaches back into the Framework DB to update the specific control
                notion.pages.update(
                    page_id=page_id,
                    properties={
                        "Status": {"select": {"name": "Evidence Pending"}},
                        "Last Evidence": {"url": log_page_url}
                    }
                )
                print(f"📡 GRC UPDATE: {cid} marked 'Evidence Pending' with log link.")
            except Exception as e:
                print(f"⚠️  GRC Update failed for {cid}: {e}")
        else:
            # This triggers if your text file has an ID that isn't in Notion yet
            print(f"⚠️  GRC Skip: {cid} not found in CMMC Cache. No status updated.")

# ─── PARSING ──────────────────────────────────────────────────────────────────

def parse_records(file_path: Path) -> List[dict]:
    if not file_path.exists():
        print(f"❌ Input file not found: {file_path}")
        return []

    content = scrub(file_path.read_text(encoding="utf-8"))
    blocks = re.findall(
        r'===INTEL_RECORD_START===(.*?)===INTEL_RECORD_END===',
        content, re.DOTALL
    )

    records = []
    for block in blocks:
        raw = {}
        for line in block.strip().split('\n'):
            if '::' in line:
                k, v = line.split('::', 1)
                raw_key = k.strip()
                clean_key = FIELD_FIXES.get(raw_key, raw_key)
                raw[clean_key] = v.strip()
        if raw.get('record_id'):
            records.append(raw)

    return records

# ─── PUSH TO NOTION ───────────────────────────────────────────────────────────

def push_record(record: dict, source_label: str, url: str) -> bool:
    record_id = record.get("record_id", "unknown")

    # Base properties with defaults for commonly missing fields
    props = {
        "Title":        {"title": to_text(f"{source_label} - {record_id}")},
        "url":          {"url": url},
        "date_watched": {"date": {"start": date.today().isoformat()}},
        "cpe_credits":  {"number": 0.75 if "Simply" in source_label else 0.5},
        "record_id":    {"rich_text": to_text(record_id)},
        "cpe_category": {"select": to_select(record.get("cpe_category", "Technical"))},
        "content_type": {"multi_select": to_multi(record.get("content_type", "Video"))},
    }

    # Process remaining fields
    for key, val in record.items():
        if key in SKIP or not val:
            continue
        if key in props:
            continue

        if key in SELECT:
            props[key] = {"select": to_select(val)}

        elif key in MULTI_SELECT:
            props[key] = {"multi_select": to_multi(val)}

        elif key in DATE_FIELDS:
            props[key] = {"date": {"start": str(val)[:10]}}

        elif key == "risk_severity_score":
            try:
                props[key] = {"number": float(val)}
            except ValueError:
                print(f"⚠️  Could not parse risk_severity_score: {val}")

        elif key in RICH_TEXT_FIELDS:
            props[key] = {"rich_text": to_text(val)}

        else:
            print(f"⚠️  Unknown field skipped: {repr(key)} = {repr(val)}")

    # CMMC Relations
    cmmc_raw = record.get("cmmc_mapping", "")
    if cmmc_raw:
        control_ids = [x.strip() for x in cmmc_raw.split(",") if x.strip()]
        relations = [
            {"id": CMMC_CACHE[cid]}
            for cid in control_ids
            if cid in CMMC_CACHE
        ]
        if relations:
            props["Master Frameworks(CMMC 2.0 / NIST 800-171)"] = {"relation": relations}
        missing = [cid for cid in control_ids if cid not in CMMC_CACHE]
        if missing:
            print(f"⚠️  CMMC IDs not found in cache: {missing}")

    try:
        # 1. Create the page and capture the response
        response = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=props
        )
        
        # 2. Get the new page URL for evidence linking
        log_url = response.get("url")
        
        # 3. Trigger the GRC Write-Back (The "Evidence Blade")
        if cmmc_raw and log_url:
            control_ids = [x.strip() for x in cmmc_raw.split(",") if x.strip()]
            update_compliance_status(control_ids, log_url)

        print(f"✅ Logged: {record_id}")
        return True

    except Exception as e:
        print(f"❌ Failed: {record_id} | {e}")
        return False

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("🛡️  STAR CPE LOGGER V5.3 — PROJECT DARKSWORD")
    print("="*55)

    while True:
        print("\n1. Simply Cyber  |  2. Barricade (DFIR)  |  3. Exit")
        choice = input("\nSelection: ").strip()

        if choice == "3":
            print("👋 Exiting.")
            break

        if choice not in ("1", "2"):
            print("❌ Invalid selection.")
            continue

        is_dfir = (choice == "2")
        source_label = "Barricade" if is_dfir else "Daily Threat Brief"
        target_file = SCRIPT_DIR / ("barricade_input.txt" if is_dfir else "governance_input.txt")

        url = input("Source URL: ").strip()
        if not url:
            print("❌ URL required.")
            continue

        print(f"\n👉 Save AI output to: {target_file.name}")
        input("Press ENTER when ready...")

        load_cmmc_cache()

        records = parse_records(target_file)
        if not records:
            print("⚠️  No records found. Check input file format.")
            continue

        print(f"\n🚀 Logging {len(records)} record(s)...")
        success = sum(
            push_record(r, source_label, url)
            for r in records
        )
        print(f"\n📊 SUMMARY: {success}/{len(records)} logged successfully.")

if __name__ == "__main__":
    main()