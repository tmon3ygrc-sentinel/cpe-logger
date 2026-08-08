"""
STAR Threat Ingest — Strategic Architecture Database
Barricade Cyber → Claude AI → Notion STAR DB
Non-Repudiation Build: Digital Fingerprinting & Audit Logging
"""

import os
import re
import json
import hashlib
import time
import datetime
from typing import Dict
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
STAR_DB_ID_PREFIX_CACHE: Dict[str, int] = {}


class DedupCheckError(RuntimeError):
    """Raised when the STAR DB dedup query cannot be completed after
    retries. Callers must fail CLOSED — treat as unresolved, not as
    'not a duplicate' — never assume absence on a query we couldn't
    actually run."""
    pass

# ─── TRANSCRIPT ───────────────────────────────────────────────────────────────

def get_transcript(url: str) -> str:
    """Fetch YouTube transcript from a video URL."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    video_id = extract_video_id(url)
    try:
        segments = YouTubeTranscriptApi().fetch(video_id)
        return " ".join(s.text for s in segments)
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

{{
  "title": "Concise concept title (max 80 chars)",
  "pillars": ["Strategic Pillar 1", "Strategic Pillar 2"],
  "hot_take": "1-2 sentence vCISO-grade insight. Be direct and opinionated. Focus on the strategic implication, not just the description.",
  "maturity": "One of exactly: L1, L2, L3, L4 (short form only — L1=Initial/Ad-hoc, L2=Documented/Defined, L3=Repeatable/Managed, L4=Adaptive/Proactive)",
  "horizon": "One of: Immediate | Short-term | Mid-Term | Long-Term",
  "cmmc": "Comma-separated CMMC 2.0 control IDs if applicable, e.g. AC.L2-3.1.1, IA.L2-3.5.3. Empty string if none."
}}

Valid Strategic Pillars (use only these — must match the live Notion field exactly):
Resilience, Supply Chain, Identity, Automation, Mobile Security, Vulnerability Management

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

def load_cmmc_cache(retries: int = 3, delay: int = 15):
    """Load CMMC control IDs into memory for relation lookups.
    Retries up to `retries` times on transient failures before giving up."""
    for attempt in range(1, retries + 1):
        print(f"📡 Querying Master Frameworks (attempt {attempt}/{retries}): {CMMC_DB_ID[:8]}...")
        try:
            has_more = True
            cursor   = None
            while has_more:
                params = {"database_id": CMMC_DB_ID.strip(), "page_size": 100}
                if cursor:
                    params["start_cursor"] = cursor
                res = notion.databases.query(**params)
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
            return
        except Exception as e:
            if attempt < retries:
                print(f"⏳ CMMC cache error (attempt {attempt}/{retries}) — retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                print(f"❌ CMMC cache failed after {retries} attempts: {e}")

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

def count_existing_star_ids_with_prefix(prefix: str, max_retries: int = 3, delay: float = 2.0) -> int:
    """Counts live STAR DB rows whose STAR ID starts with prefix. Fails
    CLOSED — raises DedupCheckError after retries rather than assuming 0
    (assuming 0 on a failed query would let the sequence restart and
    collide with real existing records)."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            res = notion.databases.query(
                database_id=STAR_DB_ID,
                filter={"property": "STAR ID", "rich_text": {"starts_with": prefix}}
            )
            return len(res.get("results", []))
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⚠️  Prefix count query failed (attempt {attempt}/{max_retries}): {e} — retrying in {delay}s")
                time.sleep(delay)
    raise DedupCheckError(f"Prefix count query failed after {max_retries} attempts: {last_exc}")


def construct_star_id(real_date: str | None = None) -> str:
    """Deterministically builds STAR ID: barricadecyber-{date}-{seq:02d}.
    Falls back to today's run date when no real published date is
    available (get_transcript() doesn't currently carry one — same
    fallback v7 uses for its manual-ingest path)."""
    date_part = real_date or datetime.date.today().isoformat()
    prefix = f"barricadecyber-{date_part}"
    if prefix not in STAR_DB_ID_PREFIX_CACHE:
        STAR_DB_ID_PREFIX_CACHE[prefix] = count_existing_star_ids_with_prefix(prefix) + 1
    seq = STAR_DB_ID_PREFIX_CACHE[prefix]
    STAR_DB_ID_PREFIX_CACHE[prefix] = seq + 1
    return f"{prefix}-{seq:02d}"


def is_duplicate(star_id: str, max_retries: int = 3, delay: float = 2.0) -> bool:
    """Check if this STAR ID already exists in STAR DB. Fails CLOSED on
    real query failures: raises DedupCheckError after retries exhausted
    rather than silently returning False."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            res = notion.databases.query(
                database_id=STAR_DB_ID,
                filter={"property": "STAR ID", "rich_text": {"equals": star_id}}
            )
            return len(res.get("results", [])) > 0
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⚠️  Dedup query failed (attempt {attempt}/{max_retries}): {e} — retrying in {delay}s")
                time.sleep(delay)
    raise DedupCheckError(f"Dedup query failed after {max_retries} attempts: {last_exc}")

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
    star_id = construct_star_id(item.get("_real_date"))  # _real_date optional, not currently populated by any caller

    try:
        if is_duplicate(star_id):
            print(f"⏭️  Skipping duplicate: {star_id} ({title})")
            return False
    except DedupCheckError as e:
        print(f"❌ DEDUP-CHECK-FAILED: {star_id} ({title}) | {e}")
        print(f"   Not pushed — dedup status unknown, not assumed new. Re-run to retry.")
        return False

    item["url"] = item.get("url") or url
    fingerprint = generate_fingerprint(item)

    properties = {
        "Topic/Concept":  {"title": [{"text": {"content": title}}]},
        "Strategic Pillar": {"multi_select": to_multi(item.get("pillars", []))},
        "vCISO Hot Take": {"rich_text": [{"text": {"content": item.get("hot_take", "")[:2000]}}]},
        "Maturity Target": {"select": {"name": item.get("maturity", "L3")}},
        "Horizon":        {"select": {"name": item.get("horizon", "Immediate")}},
        "Ingest Hash":    {"rich_text": [{"text": {"content": fingerprint}}]},
        "Operator":       {"rich_text": [{"text": {"content": OPERATOR_ID}}]},
        "STAR ID":        {"rich_text": [{"text": {"content": star_id}}]},
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
        print(f"✅ Ingested: {title} [HASH: {fingerprint[:8]}...] [STAR ID: {star_id}]")
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