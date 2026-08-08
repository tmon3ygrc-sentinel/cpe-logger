"""
STAR Threat Ingest — Strategic Architecture Database
Barricade Cyber → Claude AI → Notion STAR DB
Non-Repudiation Build: Digital Fingerprinting & Audit Logging
"""

import os
import re
import json
import hashlib
import datetime
from dotenv import load_dotenv
from notion_client import Client
import anthropic

load_dotenv()

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

NOTION_TOKEN     = os.getenv("NOTION_TOKEN")
STAR_DB_ID       = os.getenv("STAR_DS_ID") or os.getenv("NOTION_DATABASE_ID")
CMMC_DB_ID       = os.getenv("CMMC_DATABASE_ID", "32a55ed7403880b396e0de9386a76ff7")
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY")
OPERATOR_ID      = os.getenv("OPERATOR") or os.getenv("USERNAME") or "darke"

if not NOTION_TOKEN:
    raise ValueError("❌ NOTION_TOKEN missing from .env")

notion    = Client(auth=NOTION_TOKEN)
CMMC_CACHE = {}

# ─── TRANSCRIPT ───────────────────────────────────────────────────────────────

def get_transcript(url: str) -> str:
    """Fetch YouTube transcript from a video URL."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    video_id = extract_video_id(url)
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(s["text"] for s in segments)
    except NoTranscriptFound:
        raise ValueError(f"❌ No transcript found for video: {video_id}")
    except TranscriptsDisabled:
        raise ValueError(f"❌ Transcripts disabled for video: {video_id}")

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|youtu\.be/|live/)([a-zA-Z0-9_-]{11})",
        r"([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"❌ Could not extract video ID from: {url}")

# ─── CLAUDE ANALYSIS ──────────────────────────────────────────────────────────

STAR_PROMPT = """You are a vCISO-level strategic analyst extracting intelligence from cybersecurity content.

Your job is to identify distinct strategic concepts, architectural decisions, or security lessons from this transcript and structure them for a GRC Strategy & Architecture database.

Think like a seasoned vCISO: what are the durable, actionable strategic takeaways a security leader should internalize from this content?

Return a JSON array of items. Each item must have exactly these fields:

{
  "title": "Concise concept title (max 80 chars)",
  "pillars": ["Strategic Pillar 1", "Strategic Pillar 2"],
  "hot_take": "1-2 sentence vCISO-grade insight. Be direct and opinionated. Focus on the strategic implication, not just the description.",
  "maturity": "One of: L1 - Initial/Ad-hoc | L2 - Documented/Defined | L3 - Repeatable/Managed | L4 - Adaptive/Proactive",
  "horizon": "One of: Immediate | Mid-Term | Long-Term",
  "cmmc": "Comma-separated CMMC 2.0 control IDs if applicable, e.g. AC.L2-3.1.1, IA.L2-3.5.3. Empty string if none."
}

Valid Strategic Pillars (use only these):
Identity, Supply Chain, Resilience, Vulnerability Management, Incident Response,
Threat Intelligence, Cloud Security, Endpoint Security, Governance & Compliance,
Zero Trust, Automation, DFIR, Network Security, Mobile Security, Data Protection

Rules:
- Extract 2-6 distinct strategic items per video. Quality over quantity.
- Each item must represent a standalone, reusable concept — not just a summary of the video.
- hot_take must be opinionated and analyst-grade, not generic.
- Return ONLY the JSON array. No preamble, no markdown, no explanation.

Today's date: {date}
Source URL: {url}

Transcript:
{transcript}"""

def analyze_with_claude(transcript: str, url: str) -> list:
    """Send transcript to Claude and return parsed STAR items."""
    if not ANTHROPIC_KEY:
        raise ValueError("❌ Missing ANTHROPIC_API_KEY in .env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    today  = datetime.date.today().isoformat()

    print("🤖 Sending to Claude for strategic analysis...")

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": STAR_PROMPT.format(
                date=today,
                url=url,
                transcript=transcript[:12000]
            )
        }]
    )

    raw = message.content[0].text.strip()

    try:
        items = json.loads(raw)
        print(f"✅ Claude extracted {len(items)} strategic item(s)")
        return items
    except json.JSONDecodeError:
        # Try stripping markdown fences if present
        clean = re.sub(r"```json|```", "", raw).strip()
        items = json.loads(clean)
        print(f"✅ Claude extracted {len(items)} strategic item(s)")
        return items

# ─── CMMC CACHE ───────────────────────────────────────────────────────────────

def load_cmmc_cache():
    """Load CMMC control IDs into memory for relation lookups."""
    print(f"📡 Querying Master Frameworks: {CMMC_DB_ID[:8]}...")
    try:
        has_more = True
        cursor   = None
        while has_more:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            res = notion.data_sources.query(CMMC_DB_ID.strip(), **params)
            for page in res.get("results", []):
                props      = page.get("properties", {})
                title_list = props.get("Name", {}).get("title", [])
                if title_list:
                    control_id = title_list[0].get("plain_text", "").strip()
                    if control_id:
                        CMMC_CACHE[control_id] = page["id"]
            has_more = res.get("has_more", False)
            cursor   = res.get("next_cursor")

        if not CMMC_CACHE:
            print("⚠️  Cache empty — no 'Name' rows found in Master Frameworks.")
        else:
            print(f"✅ CMMC cache loaded: {len(CMMC_CACHE)} controls")
    except Exception as e:
        print(f"❌ CMMC cache failed: {e}")

def resolve_cmmc(cmmc_raw: str) -> list:
    """Resolve CMMC control ID strings to Notion page relation objects."""
    if not cmmc_raw or not CMMC_CACHE:
        return []
    control_ids = re.findall(r'[A-Z]{2,3}\.L[1-3]-[0-9.]+', cmmc_raw)
    relations   = [{"id": CMMC_CACHE[cid]} for cid in control_ids if cid in CMMC_CACHE]
    missing     = [cid for cid in control_ids if cid not in CMMC_CACHE]
    if missing:
        print(f"   ⚠️  Unresolved CMMC IDs: {missing}")
    return relations

# ─── NON-REPUDIATION ──────────────────────────────────────────────────────────

def generate_fingerprint(item: dict) -> str:
    """SHA256 hash of payload for data integrity."""
    payload = f"{item.get('title')}{item.get('hot_take')}{item.get('url', '')}"
    return hashlib.sha256(payload.encode()).hexdigest()

# ─── DE-DUPLICATION ───────────────────────────────────────────────────────────

def is_duplicate(title: str) -> bool:
    """Check if topic already exists in STAR DB by title match."""
    try:
        res = notion.data_sources.query(
            STAR_DB_ID,
            filter={"property": "Topic/Concept", "title": {"equals": title}}
)
        return len(res.get("results", [])) > 0
    except Exception:
        return False

# ─── UTILITIES ────────────────────────────────────────────────────────────────

def to_multi(values) -> list:
    """Convert list or comma string to Notion multi_select format."""
    if not values:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return [{"name": v} for v in values if v]

# ─── INGEST ───────────────────────────────────────────────────────────────────

def ingest(item: dict, url: str) -> bool:
    """Push a single STAR item to Notion with audit trail."""
    title = item.get("title", "Untitled")

    if is_duplicate(title):
        print(f"⏭️  Skipping duplicate: {title}")
        return False

    item["url"] = item.get("url") or url
    fingerprint = generate_fingerprint(item)

    properties = {
        "Topic/Concept":  {"title": [{"text": {"content": title}}]},
        "Strategic Pillar": {"multi_select": to_multi(item.get("pillars", []))},
        "vCISO Hot Take": {"rich_text": [{"text": {"content": item.get("hot_take", "")[:2000]}}]},
        "Maturity Target": {"select": {"name": item.get("maturity", "L3 - Repeatable/Managed")}},
        "Horizon":        {"select": {"name": item.get("horizon", "Immediate")}},
        "Ingest Hash":    {"rich_text": [{"text": {"content": fingerprint}}]},
        "Operator":       {"rich_text": [{"text": {"content": OPERATOR_ID}}]},
    }

    if item.get("url"):
        properties["Source URL"] = {"url": item["url"]}

    cmmc_rels = resolve_cmmc(item.get("cmmc", ""))
    if cmmc_rels:
        properties["CMMC Family"] = {"relation": cmmc_rels}
        print(f"   🔗 Linked {len(cmmc_rels)} CMMC control(s)")

    try:
        notion.pages.create(
            parent={"database_id": STAR_DB_ID},
            properties=properties
        )
        print(f"✅ Ingested: {title} [HASH: {fingerprint[:8]}...]")
        return True
    except Exception as e:
        print(f"❌ Failed: {title} | {e}")
        return False

def ingest_all(items: list, url: str):
    """Push all items and print summary."""
    print(f"\n📋 Pushing {len(items)} item(s) to Notion...\n")
    success = sum(ingest(item, url) for item in items)
    print(f"\n{'='*65}")
    print(f"📊 SUMMARY: {success}/{len(items)} items ingested as Operator: {OPERATOR_ID}")
    print("="*65)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*65)
    print("⚔️   PROJECT DARKSWORD — STAR STRATEGY ENGINE")
    print("     Barricade Cyber → Claude AI → Notion")
    print("="*65)

    load_cmmc_cache()

    print("\n1. Autonomous Pipeline  (YouTube → Claude → Notion)")
    print("0. Exit")
    choice = input("\nSelection: ").strip()

    if choice == "1":
        url = input("YouTube URL: ").strip()
        if not url:
            print("❌ No URL provided.")
        else:
            try:
                print("📡 Fetching transcript...")
                transcript = get_transcript(url)
                print(f"✅ Transcript fetched ({len(transcript)} chars)")
                items = analyze_with_claude(transcript, url)
                ingest_all(items, url)
            except Exception as e:
                print(f"❌ Pipeline failed: {e}")

    elif choice == "0":
        print("👋 Exiting.")