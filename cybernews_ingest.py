# cybernews_ingest.py
# Cybernews Podcast -> STAR_STRATEGY_DB_V2 + Threat Actor Registry ingest pipeline.
# Phase 2 of the Cybernews 88-episode backfill (Phase 1 = cybernews_transcribe.py,
# already complete: 88/88 transcripts on disk, data/cybernews_transcripts/manifest.json).
# See boards/BOARD.md (2026-08-18 entries) and boards/cybernews_ingest_scope.md
# (the OPS handoff this implements) for full context.
#
# Built by copying darknetdiaries_ingest.py (RSS/cursor pattern) and
# crowdstrike_ingest.py (disk-transcript-load + Source-URL-dedup pattern), per
# the handoff's explicit instruction -- not a novel architecture. scrub(),
# sanitize_multi_select(), _to_multi_select(), normalize_actor_key(),
# _build_actor_cache(), resolve_actor() copied verbatim from
# darknetdiaries_ingest.py, not reimplemented.
#
# --- Corrections found during Gate 1 prereq verification, not in the handoff
#     doc as written, live-verified before writing any of this ---
#
# 1. Notion IDs: the handoff lists collection:// (data-source) IDs. Both prior
#    ingest builds independently found notion-client==2.2.1's databases.query()/
#    pages.create() reject those -- the underlying database-OBJECT id is
#    required. Re-verified live this session. Using the same IDs
#    darknetdiaries_ingest.py/crowdstrike_ingest.py already use:
#      STAR_STRATEGY_DB_V2   -> 33a55ed7403880e29152d1997bc01f64
#      Threat Actor Registry -> c46125e586b3488dbc27518c245cf7fc
#
# 2. Field names: handoff says "Source"/"Maturity" -- neither exists on the
#    live schema (re-fetched live this session). Live fields are
#    "Source URL" (url type) and "Maturity Target" (select, "L2" confirmed
#    valid) -- same correction darknetdiaries_ingest.py already made
#    independently. "Episode Number" (number) and "vCISO Hot Take" (text)
#    exist as-named. "Victim Org" / "victim_org" confirmed ABSENT from the
#    live schema -- omitted per the handoff's own instruction, not written.
#
# 3. episode_number is null for 37/88 episodes (42%), not a minority "EP?
#    case" as the handoff's phrasing implied -- confirmed by reading the live
#    manifest before writing the cursor logic. Source URL dedup is therefore
#    the PRIMARY, universal dedup gate here (checked for every episode,
#    numbered or not); the numeric Episode-Number cursor is a secondary,
#    reporting-only signal, not a second independent skip authority -- see
#    get_existing_max_episode()'s docstring for why maintaining two
#    independently-imperfect gates that could disagree was rejected in favor
#    of one ground-truth check.
#
# 4. get_existing_max_episode() cannot reuse darknetdiaries_ingest.py's
#    literal query (a DB-wide max, no source filter) -- STAR_STRATEGY_DB_V2
#    is shared across DD/CrowdStrike/Cybernews, and DD's Episode Number range
#    (1-179) overlaps Cybernews's (1-~88). An unfiltered max would treat
#    Cybernews episodes as already-ingested purely because DD had already
#    pushed a numerically-higher episode. Filtered here to rows whose
#    Source URL contains the Cybernews show's stable Anchor ID ("d69ab560"),
#    confirmed present in all 88 manifest audio_urls before relying on it.

import os
import re
import json
import time
import argparse
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from notion_client import Client
import anthropic

load_dotenv()


# scrub() copied verbatim from darknetdiaries_ingest.py (itself copied from
# notion_logger_v7.py) -- see that file's header for why this is copied
# rather than imported.
def scrub(text: str) -> str:
    """
    Cleans transcript/show notes artifacts from raw fetched text.

    SAFE removals:
      - INTEL_RECORD markers (injection defense pre-flight)
      - Timestamps: "0:00", "12:34"
      - Excess whitespace

    NOT removed (would destroy intel):
      - Brackets like [MITRE T1190], [CVE-2024-1234], [CISA KEV]
    """
    text = re.sub(r'===INTEL_RECORD_(?:START|END)===', '', text)
    text = re.sub(r'\b\d+:\d{2}\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ─── CONFIGURATION ──────────────────────────────────────────────────────────

NOTION_TOKEN      = os.getenv("NOTION_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

RSS_URL          = "https://anchor.fm/s/d69ab560/podcast/rss"
CYBERNEWS_SHOW_ID = "d69ab560"  # stable across all 88 manifest audio_urls, confirmed live

TRANSCRIPT_DIR = Path(__file__).parent / "data" / "cybernews_transcripts"
MANIFEST_PATH  = TRANSCRIPT_DIR / "manifest.json"

# Avg episode is 43min (~34,400 chars at the observed ~800 chars/min rate from
# the two Phase-1 spot-check transcripts: 38,835 chars/49min, 34,164 chars/
# 42min) -- 50000 covers the average episode whole. The longest episode
# (80.9min, confirmed via manifest scan) runs ~65k chars and will be
# truncated by this cap; accepted, not hidden -- a full-episode outlier
# losing its closing ~20% still yields a usable topic/summary/TTP extraction
# from the rest, same tradeoff class darknetdiaries_ingest.py made at a much
# tighter 15000-char cap for its larger 168-episode backfill.
TRANSCRIPT_CHAR_LIMIT = 50000

# NOTE: same live database-OBJECT ids as darknetdiaries_ingest.py/
# crowdstrike_ingest.py (not the collection:// data-source ids) -- see file
# header, correction #1.
STAR_DB_ID        = "33a55ed7403880e29152d1997bc01f64"
ACTOR_REGISTRY_ID = "c46125e586b3488dbc27518c245cf7fc"

if not NOTION_TOKEN:
    raise ValueError("NOTION_TOKEN missing from .env")

notion = Client(auth=NOTION_TOKEN)


class DedupCheckError(RuntimeError):
    """Raised when a Notion read that gates dedup/cursor state can't be
    completed after retries. Fail CLOSED, mirroring darknetdiaries_ingest.py/
    crowdstrike_ingest.py -- never assume an empty/zero result on a query
    that actually failed."""
    pass


# ─── STAGE 1 -- MANIFEST / RSS LOAD ──────────────────────────────────────────

def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _safe_int(s: str):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_duration(s: str) -> int:
    if not s:
        return 0
    parts = s.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(s))
    except ValueError:
        return 0


NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "atom":   "http://www.w3.org/2005/Atom",
}


def fetch_rss() -> List[dict]:
    """Live RSS refetch -- same parse shape as cybernews_transcribe.py's own
    fetch_rss() (copied, not imported, matching this project's standalone-
    script convention), so a refresh produces manifest-compatible entries.
    Oldest-first, matching Phase 1's checkpoint-progress ordering."""
    with urllib.request.urlopen(RSS_URL, timeout=30) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("No <channel> element found in RSS")

    episodes = []
    for item in channel.findall("item"):
        enc_el = item.find("enclosure")
        guid_el = item.find("guid")
        if enc_el is None or not _text(guid_el):
            continue
        episodes.append({
            "guid":             _text(guid_el),
            "episode_number":   _safe_int(_text(item.find("itunes:episode", NS))),
            "title":            _text(item.find("title")),
            "audio_url":        enc_el.attrib.get("url", ""),
            "pub_date":         _text(item.find("pubDate")),
            "duration_seconds": _parse_duration(_text(item.find("itunes:duration", NS))),
            "link":             _text(item.find("link")),
        })
    episodes.sort(key=lambda e: e["pub_date"])
    return episodes


def load_manifest() -> List[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def write_manifest(episodes: List[dict]) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)


# ─── STAGE 2 -- TRANSCRIPT LOAD FROM DISK ───────────────────────────────────

def load_transcript(guid: str) -> Optional[str]:
    """Read the Phase-1 Whisper transcript for one episode from disk. GUID
    sanitization matches transcript_path() in cybernews_transcribe.py exactly
    (same re.sub(r"[^\\w\\-]", "_", guid) pattern) -- verified against a real
    manifest GUID before writing this function. Returns None (not an
    exception) on a missing file, matching darknetdiaries_ingest.py/
    crowdstrike_ingest.py's per-episode skip-on-missing behavior."""
    safe_guid = re.sub(r'[^\w\-]', '_', guid)
    p = TRANSCRIPT_DIR / f"{safe_guid}.txt"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip()


# ─── STAGE 3 -- CURSOR / DEDUP ───────────────────────────────────────────────

def get_existing_max_episode(max_retries: int = 3, delay: float = 2.0) -> int:
    """Return the highest Episode Number already in STAR_STRATEGY_DB_V2 among
    rows whose Source URL is a Cybernews episode (Source URL contains the
    show's stable Anchor ID, CYBERNEWS_SHOW_ID) -- NOT a DB-wide max. See file
    header, correction #4: this DB is shared with Darknet Diaries (episode
    numbers up to 179) and an unfiltered max would falsely treat Cybernews
    episodes as already-ingested. Reporting/pre-filter signal only -- the
    actual per-episode skip decision is Source URL cache membership
    (_build_source_url_cache), which is correct for both numbered and
    null-numbered episodes; this cursor cannot be, since 37/88 episodes have
    no Episode Number to compare. Fails CLOSED like the sibling scripts."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            max_ep = 0
            has_more = True
            cursor = None
            while has_more:
                params = {"database_id": STAR_DB_ID, "page_size": 100}
                if cursor:
                    params["start_cursor"] = cursor
                res = notion.databases.query(**params)
                for page in res.get("results", []):
                    props = page.get("properties", {})
                    src_url = props.get("Source URL", {}).get("url") or ""
                    if CYBERNEWS_SHOW_ID not in src_url:
                        continue
                    num = props.get("Episode Number", {}).get("number")
                    if isinstance(num, (int, float)) and num > max_ep:
                        max_ep = int(num)
                has_more = res.get("has_more", False)
                cursor = res.get("next_cursor")
            return max_ep
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⏳ Cursor query failed (attempt {attempt}/{max_retries}) -- retrying in {delay}s: {e}")
                time.sleep(delay)
    raise DedupCheckError(f"get_existing_max_episode failed after {max_retries} attempts: {last_exc}")


def _build_source_url_cache(max_retries: int = 3, delay: float = 2.0) -> set:
    """Pre-load every existing Source URL already in STAR_STRATEGY_DB_V2 into
    a set -- one paginated startup query, not a per-row call inside the main
    loop (AO-confirmed requirement). Copied pattern from
    crowdstrike_ingest.py's _build_source_url_cache(). This is the PRIMARY,
    universal dedup gate for this script (see correction #3) -- correct for
    both numbered and null-numbered episodes alike, unlike the Episode-Number
    cursor above. Fails CLOSED: an empty set on a failed query would look
    identical to "nothing pushed yet" and re-push the entire backfill."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            urls: set = set()
            has_more = True
            cursor = None
            while has_more:
                params = {"database_id": STAR_DB_ID, "page_size": 100}
                if cursor:
                    params["start_cursor"] = cursor
                res = notion.databases.query(**params)
                for page in res.get("results", []):
                    url = page.get("properties", {}).get("Source URL", {}).get("url")
                    if url:
                        urls.add(url)
                has_more = res.get("has_more", False)
                cursor = res.get("next_cursor")
            return urls
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⏳ Source URL cache query failed (attempt {attempt}/{max_retries}) -- retrying in {delay}s: {e}")
                time.sleep(delay)
    raise DedupCheckError(f"_build_source_url_cache failed after {max_retries} attempts: {last_exc}")


# ─── STAGE 4 -- CLAUDE EXTRACTION ───────────────────────────────────────────

CN_PROMPT = """You are a vCISO-level GRC intelligence analyst extracting structured data from a Cybernews podcast transcript.

Episode title: {title}

Analyze the transcript below and return a single JSON object with exactly these fields:

{{
  "topic_concept": "string -- one sentence summary of what this episode is about",
  "threat_actor_name": "string or null -- canonical name of the primary threat actor/group/individual featured, null if none",
  "threat_actor_type": "one of: individual, group, nation-state, unknown -- or null if no actor",
  "is_threat_actor": true or false,
  "victim_org": "string or null -- primary victim organization named in the episode, null if none",
  "attack_techniques": ["array of strings -- MITRE ATT&CK-style technique names or descriptions, empty array if none"],
  "kill_chain_phase": "string -- dominant kill chain phase this episode illustrates (e.g. Initial Access, Exfiltration, Impact), or 'N/A' if not applicable",
  "control_domains": ["array of strings -- GRC control domains this episode is relevant to (e.g. Identity, Supply Chain, Physical Security)"],
  "ttps_summary": "string -- 2-3 sentence narrative summary of what happened / what this episode covers"
}}

Rules:
- is_threat_actor should be true only if a specific, nameable actor/group/individual is the clear subject of the episode -- not for general tech-culture, AI-ethics, or media-commentary episodes (e.g. Black Mirror reviews) with no clear actor.
- This show's content mix is uneven -- some episodes are threat-actor-dense news coverage, others are general tech/AI/culture commentary with no security angle at all. Do not force-fit an actor or techniques onto an episode that doesn't have them; low/zero-signal extraction is a correct and expected result for those episodes, not a failure.
- Return ONLY the JSON object. No preamble, no markdown fences, no explanation.

Transcript (may be truncated):
{transcript}"""


def extract_fields_claude(title: str, transcript: str) -> dict:
    """Send transcript to Claude and return the parsed STAR/actor field dict.
    Returns {} on any parse failure -- logs the raw response, never crashes
    the run over one bad episode."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY in .env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = CN_PROMPT.format(title=title, transcript=transcript[:TRANSCRIPT_CHAR_LIMIT])

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            print(f"❌ Claude extraction JSON parse failed for '{title}': {e}")
            print(f"   Raw response (first 500 chars): {raw[:500]}")
            return {}


# ─── STAGE 5 -- resolve_actor() ─────────────────────────────────────────────
# Copied verbatim from darknetdiaries_ingest.py, per the handoff's explicit
# instruction -- not reimplemented.

def normalize_actor_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_actor_cache(max_retries: int = 3, delay: float = 2.0) -> Dict[str, str]:
    """Pre-load the Threat Actor Registry into a normalized-key -> page_id
    cache: one query covers canonical_name AND every comma-split alias, so an
    actor already in the Registry from ANY prior pipeline (DD, CrowdStrike)
    is found and reused rather than duplicated. Fails CLOSED: raises
    DedupCheckError rather than returning an empty cache on a failed query."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            cache: Dict[str, str] = {}
            has_more = True
            cursor = None
            while has_more:
                params = {"database_id": ACTOR_REGISTRY_ID, "page_size": 100}
                if cursor:
                    params["start_cursor"] = cursor
                res = notion.databases.query(**params)
                for page in res.get("results", []):
                    props = page.get("properties", {})
                    title_list = props.get("canonical_name", {}).get("title", [])
                    canonical = title_list[0].get("plain_text", "").strip() if title_list else ""
                    if canonical:
                        cache[normalize_actor_key(canonical)] = page["id"]
                    aliases_rt = props.get("aliases", {}).get("rich_text", [])
                    aliases_raw = "".join(t.get("plain_text", "") for t in aliases_rt)
                    for alias in aliases_raw.split(","):
                        alias = alias.strip()
                        if alias:
                            cache[normalize_actor_key(alias)] = page["id"]
                has_more = res.get("has_more", False)
                cursor = res.get("next_cursor")
            return cache
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⏳ Actor cache query failed (attempt {attempt}/{max_retries}) -- retrying in {delay}s: {e}")
                time.sleep(delay)
    raise DedupCheckError(f"_build_actor_cache failed after {max_retries} attempts: {last_exc}")


def resolve_actor(name: str, actor_cache: dict, dry_run: bool = False) -> str:
    """Returns Notion page ID of the actor row, creating a stub if absent."""
    key = normalize_actor_key(name)
    if key in actor_cache:
        print(f"   ✅ Reusing existing Threat Actor Registry entry for {name} (no duplicate created)")
        return actor_cache[key]

    if dry_run:
        fake_id = f"DRY-RUN-NEW-ACTOR::{name}"
        actor_cache[key] = fake_id
        print(f"   [DRY RUN] would create Threat Actor Registry stub: {name}")
        return fake_id

    today = datetime.date.today().isoformat()
    properties = {
        "canonical_name": {"title": [{"text": {"content": name}}]},
        "classification": {"select": {"name": "unknown-unattributed"}},
        "attributed_nation_state": {"select": {"name": "unknown"}},
        "active": {"checkbox": True},
        "analyst_notes": {"rich_text": [{"text": {"content": f"Cybernews auto-create, {today}"}}]},
    }
    response = notion.pages.create(parent={"database_id": ACTOR_REGISTRY_ID}, properties=properties)
    page_id = response["id"]
    actor_cache[key] = page_id
    print(f"   \U0001f195 Created Threat Actor Registry stub: {name}")
    return page_id


# ─── STAGE 6 -- STAR ROW PUSH ────────────────────────────────────────────────
# sanitize_multi_select() / _to_multi_select() copied verbatim from
# darknetdiaries_ingest.py.

def sanitize_multi_select(items: list) -> list:
    """Strip parenthetical clauses from each item before it becomes a Notion
    multi_select option name -- Notion's API hard-rejects commas inside a
    multi_select option name (live-confirmed on the DD backfill: EP10/102/
    104/126 lost their whole row on this exception)."""
    return [re.sub(r'\s*\(.*?\)', '', str(item)).strip() for item in items]


def _to_multi_select(values) -> list:
    if not values:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return [{"name": str(v)} for v in values if v]


def push_star_row(fields: dict, actor_page_id: Optional[str], ep: dict,
                   dry_run: bool = False) -> bool:
    """Push a single STAR row for one Cybernews episode.

    Field mapping (live-schema-confirmed, see file header correction #2):
    Source -> Source URL (audio_url from manifest, per handoff's explicit
    "MP3 audio URL, not the web page" decision -- the web page 403s to
    scrapers); Maturity -> Maturity Target "L2"; TTPs Summary -> vCISO Hot
    Take; Episode Number -> ep["episode_number"] (may be None -- Notion's
    number property accepts null). No Victim Org field exists on the live
    schema -- omitted, not written, not erroring.
    """
    title = fields.get("topic_concept") or ep.get("title") or f"Cybernews {ep.get('guid', '')[:8]}"
    ep_num = ep.get("episode_number")
    audio_url = ep.get("audio_url")
    victim_org = fields.get("victim_org")

    if dry_run:
        print(f"   [DRY RUN] would push STAR row:")
        print(f"     Topic/Concept: {title}")
        print(f"     Episode Number: {ep_num}")
        print(f"     Source URL: {audio_url}")
        print(f"     Threat Actors: {[actor_page_id] if actor_page_id else []}")
        print(f"     attack_techniques: {fields.get('attack_techniques', [])}")
        print(f"     kill_chain_phase: {fields.get('kill_chain_phase')}")
        print(f"     control_domains: {fields.get('control_domains', [])}")
        print(f"     Maturity Target: L2")
        print(f"     vCISO Hot Take: {fields.get('ttps_summary', '')[:200]}")
        print(f"     Victim Org (omitted, no live property): {victim_org}")
        return True

    properties = {
        "Topic/Concept":   {"title": [{"text": {"content": title[:2000]}}]},
        "Episode Number":  {"number": ep_num},
        "Maturity Target": {"select": {"name": "L2"}},
    }
    if audio_url:
        properties["Source URL"] = {"url": audio_url}
    if actor_page_id:
        properties["Threat Actors"] = {"relation": [{"id": actor_page_id}]}
    if fields.get("attack_techniques"):
        properties["attack_techniques"] = {"multi_select": _to_multi_select(sanitize_multi_select(fields["attack_techniques"]))}
    if fields.get("kill_chain_phase"):
        properties["kill_chain_phase"] = {"select": {"name": str(fields["kill_chain_phase"])[:100]}}
    if fields.get("control_domains"):
        properties["control_domains"] = {"multi_select": _to_multi_select(fields["control_domains"])}
    if fields.get("ttps_summary"):
        properties["vCISO Hot Take"] = {"rich_text": [{"text": {"content": fields["ttps_summary"][:2000]}}]}

    try:
        notion.pages.create(parent={"database_id": STAR_DB_ID}, properties=properties)
        return True
    except Exception as e:
        print(f"❌ Failed to push {ep.get('guid')} ({title}): {e}")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cybernews -> STAR ingest pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be pushed, write nothing to Notion")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N new episodes (oldest-first)")
    parser.add_argument("--episodes", type=str, default=None,
                         help="Comma-separated GUIDs to (re)process directly, bypassing the "
                              "new-episode filter -- for targeted retries, e.g. "
                              "--episodes 584d0245-9075-4478-87e4-d70260d556f1,...")
    parser.add_argument("--skip-manifest-refresh", action="store_true",
                         help="Reuse existing manifest.json instead of re-fetching the RSS feed")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("📰  CYBERNEWS -> STAR STRATEGY ENGINE")
    if args.dry_run:
        print("     [DRY RUN -- nothing will be written to Notion]")
    if args.episodes:
        print(f"     [TARGETED RE-RUN -- {len(args.episodes.split(','))} GUID(s), new-episode filter bypassed]")
    print("=" * 65 + "\n")

    if args.skip_manifest_refresh:
        episodes = load_manifest()
        print(f"Loaded manifest: {len(episodes)} episode(s) (RSS refresh skipped)\n")
    else:
        episodes = fetch_rss()
        write_manifest(episodes)
        print(f"Refreshed manifest from RSS: {len(episodes)} episode(s)\n")

    actor_cache = _build_actor_cache()
    source_url_cache = _build_source_url_cache()
    max_ep = get_existing_max_episode()
    print(f"Existing Cybernews rows in STAR_STRATEGY_DB_V2: {len(source_url_cache & {e['audio_url'] for e in episodes})} "
          f"(via Source URL match) | max numbered episode already pushed: {max_ep}\n")

    if args.episodes:
        target_guids = {g.strip() for g in args.episodes.split(",") if g.strip()}
        new_items = [e for e in episodes if e["guid"] in target_guids]
        found = {e["guid"] for e in new_items}
        missing = target_guids - found
        if missing:
            print(f"⚠️  Requested GUID(s) not found in manifest: {sorted(missing)}\n")
    else:
        new_items = episodes  # already oldest-first; skip decision is per-item below (Source URL cache)

    if args.limit:
        new_items = new_items[:args.limit]

    print(f"Processing {len(new_items)} episode(s)\n")

    null_ep_flagged = 0
    for ep in new_items:
        guid = ep["guid"]
        ep_num = ep.get("episode_number")
        ep_label = f"EP{ep_num}" if ep_num is not None else "EP?"
        print(f"--- {ep_label} ({guid[:8]}): {ep['title']} ---")

        if ep_num is None:
            null_ep_flagged += 1
            print(f"   [null episode_number -- dedup relies solely on Source URL match for this one]")

        if ep["audio_url"] in source_url_cache:
            print(f"{ep_label}: Source URL already present in STAR_STRATEGY_DB_V2 -- already pushed, skipped\n")
            continue

        transcript_raw = load_transcript(guid)
        if transcript_raw is None:
            print(f"{ep_label}: no transcript file on disk ({guid}.txt) -- skipped\n")
            continue

        transcript = scrub(transcript_raw)
        fields = extract_fields_claude(ep["title"], transcript)
        if not fields:
            print(f"{ep_label}: extraction failed -- skipped\n")
            continue

        is_actor_ep = bool(fields.get("is_threat_actor")) and bool(fields.get("threat_actor_name"))
        if not fields.get("is_threat_actor"):
            print(f"   [non-threat-actor content -- pushing STAR row, resolve_actor() skipped]")
        low_signal = not fields.get("attack_techniques") and not fields.get("threat_actor_name")
        if low_signal:
            print(f"   [low-signal episode -- zero attack_techniques + no actor -- pushing anyway for topic_concept/ttps_summary]")

        actor_page_id = None
        if is_actor_ep:
            actor_page_id = resolve_actor(fields["threat_actor_name"], actor_cache, dry_run=args.dry_run)

        ok = push_star_row(fields, actor_page_id, ep, dry_run=args.dry_run)
        status = "[DRY RUN] would push" if args.dry_run else ("pushed" if ok else "FAILED")
        print(f"{ep_label}: {status} -- actor={fields.get('threat_actor_name')}\n")

    if null_ep_flagged:
        print(f"Note: {null_ep_flagged} episode(s) processed this run had no Episode Number "
              f"(dedup relied on Source URL match only for those).\n")


if __name__ == "__main__":
    main()
