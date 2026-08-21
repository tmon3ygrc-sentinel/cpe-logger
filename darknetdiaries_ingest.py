# darknetdiaries_ingest.py
# Darknet Diaries -> STAR_STRATEGY_DB_V2 + Threat Actor Registry ingest pipeline
#
# Design note (AO-confirmed 2026-08-10): star_threat_ingest.py was named as the
# "reference implementation" in the OPS handoff, but it does NOT actually import
# from notion_logger_v7.py, and has no resolve_actor() to copy -- both claims in
# the handoff/scope doc were checked directly and found false. AO's call: fork
# this script's own Notion client + push/resolve_actor logic (same shape as
# star_threat_ingest.py), import only scrub() from v7, do not build a shared
# push layer in v7. See boards/BOARD.md for the full Step 0 finding.
#
# Field-mapping note (AO-confirmed 2026-08-10): the STAR_STRATEGY_DB_V2 schema
# was live-checked, not trusted from the scope doc, and differs from the
# handoff's assumed shape:
#   - "Source" (text) does not exist -> using live "Source URL" (url), populated
#     from the RSS <link> for the episode.
#   - "Maturity" does not exist -> using live "Maturity Target" (select), "L2".
#   - "TTPs Summary" does not exist -> using live "vCISO Hot Take" (text).
#   - "Victim Org" does not exist -> omitted in v1 (noted in dry-run output only).
#   - "Episode Number" did not exist -> added live to STAR_STRATEGY_DB_V2 as a
#     number property on AO go-ahead before this script was written.

import os
import re
import json
import time
import argparse
import datetime
from typing import Dict, List, Optional

import requests
import feedparser
from dotenv import load_dotenv
from notion_client import Client
import anthropic

load_dotenv()

# scrub() copied (not imported) from notion_logger_v7.py -- importing that
# module top-level requires its own DATABASE_ID (the unrelated Ledger DB) to
# be set in .env and instantiates its own live Notion/Anthropic clients as an
# import-time side effect (checked directly, notion_logger_v7.py:110-130).
# 4-line pure function, copied verbatim rather than forked.
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
OPERATOR_ID       = os.getenv("OPERATOR") or os.getenv("USERNAME") or "darke"

FEED_URL           = "https://feeds.megaphone.fm/darknetdiaries"

# NOTE (2026-08-10): the handoff/scope doc/star_threat_ingest.py all hardcode
# these as the *data source* (collection://) IDs -- e.g. STAR "33a55ed7-4038-
# 802b-9f10-000b98509194". Live-tested directly: notion-client==2.2.1's
# databases.query()/pages.create() reject that ID ("Could not find database
# with ID... not shared with your integration") even freshly re-shared in the
# Notion UI -- re-sharing was a red herring. The underlying *database object*
# ID (surfaced by the MCP connector's fetch response `url` field, a different
# ID from the data-source/collection ID) works immediately, no re-share
# needed. Using the database-object IDs here, not the collection IDs.
STAR_DB_ID         = "33a55ed7403880e29152d1997bc01f64"
ACTOR_REGISTRY_ID  = "c46125e586b3488dbc27518c245cf7fc"

if not NOTION_TOKEN:
    raise ValueError("❌ NOTION_TOKEN missing from .env")

notion = Client(auth=NOTION_TOKEN)


class DedupCheckError(RuntimeError):
    """Raised when a Notion read that gates dedup/cursor state can't be
    completed after retries. Callers must fail CLOSED -- never assume an
    empty/zero result on a query that actually failed."""
    pass


# ─── STAGE 1 -- RSS FETCH & ITEM PARSING ────────────────────────────────────

def _strip_title_prefix(raw_title: str, ep_num: int) -> str:
    """Strip the feed's own leading "{ep_num}: " / "{ep_num}. " prefix from an
    episode title. Episode Number already lives in its own Notion field
    (AO fix, 2026-08-10) -- redundant in Topic/Concept otherwise. Only
    strips when the prefix matches the *actual* episode number for this
    entry, not a generic leading-digits regex, so a title that happens to
    start with an unrelated number is left alone."""
    return re.sub(rf'^\s*{ep_num}\s*[:.]\s*', '', raw_title).strip()


def fetch_rss() -> List[dict]:
    """Fetch and parse the Darknet Diaries RSS feed.

    Live-verified against the real feed (2026-08-10): items with no
    <itunes:episode> tag (the "LOW - Trailer" item, itunes:episodeType
    "trailer") are skipped -- they have no stable episode number to gate
    the cursor on. This also corrects a stale board/scope-doc claim that
    the newest item ("EP 179", Aug 6 2026) was a numbered episode; it is
    actually that trailer. The newest real numbered episode is EP178
    (Aug 4 2026). Not a blocker -- fetch_rss() naturally excludes it.
    """
    feed = feedparser.parse(FEED_URL)
    items = []
    for entry in feed.entries:
        ep_raw = entry.get("itunes_episode")
        if not ep_raw:
            continue
        try:
            ep_num = int(ep_raw)
        except (TypeError, ValueError):
            continue

        transcript = entry.get("podcast_transcript") or {}
        transcript_url = transcript.get("url") if transcript.get("type") == "text/vtt" else None

        raw_title = entry.get("title", f"Episode {ep_num}")
        items.append({
            "episode_number": ep_num,
            "title": _strip_title_prefix(raw_title, ep_num),
            "link": entry.get("link", ""),
            "pubdate": entry.get("published", ""),
            "transcript_url": transcript_url,
        })
    return items


# ─── STAGE 2 -- CURSOR / DEDUP ──────────────────────────────────────────────

def get_existing_max_episode(max_retries: int = 3, delay: float = 2.0) -> int:
    """Return the highest Episode Number already in STAR_STRATEGY_DB_V2, or 0
    if none. Fails CLOSED: raises DedupCheckError after retries rather than
    returning 0 on a failed query -- returning 0 on failure would treat every
    already-ingested episode as new and re-push the entire backfill."""
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
                    num = page.get("properties", {}).get("Episode Number", {}).get("number")
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


# ─── STAGE 3 -- VTT FETCH & STRIP ───────────────────────────────────────────

def fetch_vtt(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def strip_vtt(raw_vtt: str) -> str:
    """Strip a WEBVTT transcript down to clean speaker-labeled paragraphs.

    Deviation from the OPS handoff's literal Step 3 wording, flagged not
    silently changed: the handoff says "skip block if it contains -->
    (timestamp-only block)". Live-checked against the real EP173 VTT --
    every real cue block is [timestamp line, text line] together, so that
    instruction as literally written would strip the entire transcript to
    nothing. Implemented per the scope doc's Stage 3 description instead:
    discard only the timestamp LINE within each cue, keep the text.
    """
    blocks = raw_vtt.strip().split("\n\n")
    cues = []
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT"):
            continue
        text_lines = []
        for line in lines:
            if "-->" in line:
                continue
            if re.match(r"^\d+$", line):  # defensive: numeric cue-id lines (not present in DD's VTTs, seen in other dialects)
                continue
            text_lines.append(line)
        if text_lines:
            cues.append(" ".join(text_lines))
    return "\n".join(cues)


# ─── STAGE 4 -- CLAUDE EXTRACTION ───────────────────────────────────────────

DD_PROMPT = """You are a vCISO-level GRC intelligence analyst extracting structured data from a Darknet Diaries podcast transcript.

Episode title: {title}

Analyze the transcript below and return a single JSON object with exactly these fields:

{{
  "topic_concept": "string -- one sentence summary of what this episode is about",
  "threat_actor_name": "string or null -- canonical name of the primary threat actor/group/individual featured, null if none",
  "threat_actor_type": "one of: individual, group, nation-state, unknown -- or null if no actor",
  "is_threat_actor": true or false,
  "victim_org": "string or null -- primary victim organization named in the episode, null if none",
  "attack_techniques": ["array of strings -- MITRE ATT&CK-style technique names or descriptions"],
  "kill_chain_phase": "string -- dominant kill chain phase this episode illustrates (e.g. Initial Access, Exfiltration, Impact)",
  "control_domains": ["array of strings -- GRC control domains this episode is relevant to (e.g. Identity, Supply Chain, Physical Security)"],
  "ttps_summary": "string -- 2-3 sentence narrative summary of what happened, tactics/techniques/procedures used"
}}

Rules:
- is_threat_actor should be true only if a specific, nameable actor/group/individual is the clear subject of the episode -- not for general-interview or awareness episodes with no clear actor.
- This episode may be a historical narrative (a 1990s hack, a 2015 breach), not current news -- extract what actually happened, do not force a "recent/current" framing.
- Return ONLY the JSON object. No preamble, no markdown fences, no explanation.

Transcript (may be truncated):
{transcript}"""


def extract_fields_claude(title: str, transcript: str) -> dict:
    """Send transcript to Claude and return the parsed STAR/actor field dict.
    Returns {} on any parse failure -- logs the raw response, never crashes
    the run over one bad episode."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("❌ Missing ANTHROPIC_API_KEY in .env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = DD_PROMPT.format(title=title, transcript=transcript[:15000])

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

def normalize_actor_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_actor_cache(max_retries: int = 3, delay: float = 2.0) -> Dict[str, str]:
    """Pre-load the Threat Actor Registry into a normalized-key -> page_id
    cache: one query covers canonical_name AND every comma-split alias, so a
    same-run OR a prior-run actor is caught before falling through to a
    create. Fails CLOSED: raises DedupCheckError rather than returning an
    empty cache on a failed query (an empty cache on failure would silently
    create duplicate actor stubs for every actor already in the registry)."""
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
    """Returns Notion page ID of the actor row, creating a stub if absent.

    Deviation from the handoff's literal field list, AO-confirmed: the live
    Threat Actor Registry schema has no "Name"/"Source"/"Created" properties
    (checked directly). Maps to the real schema instead: canonical_name
    (title), classification="unknown-unattributed", attributed_nation_state
    ="unknown", active=True. Provenance ("Darknet Diaries auto-create") goes
    into analyst_notes since there's no dedicated Source field.
    """
    key = normalize_actor_key(name)
    if key in actor_cache:
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
        "analyst_notes": {"rich_text": [{"text": {"content": f"Darknet Diaries auto-create, {today}"}}]},
    }
    response = notion.pages.create(parent={"database_id": ACTOR_REGISTRY_ID}, properties=properties)
    page_id = response["id"]
    actor_cache[key] = page_id
    print(f"   \U0001f195 Created Threat Actor Registry stub: {name}")
    return page_id


# ─── STAGE 6 -- STAR ROW PUSH ────────────────────────────────────────────────

def sanitize_multi_select(items: list) -> list:
    """Strip commas (and parenthetical clauses) from each item before it
    becomes a Notion multi_select option name -- Notion's API hard-rejects
    any comma inside a multi_select value, regardless of context.
    """
    result = []
    for item in items:
        # Strip parenthetical sub-clauses first (existing logic)
        cleaned = re.sub(r'\s*\(.*?\)', '', str(item)).strip()
        # Then strip any remaining commas (bare commas outside parens,
        # e.g. "Store Now, Decrypt Later")
        cleaned = cleaned.replace(',', '')
        # Collapse any double-spaces left behind
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        if cleaned:
            result.append(cleaned)
    return result


def _to_multi_select(values) -> list:
    if not values:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return [{"name": str(v)} for v in values if v]


def push_star_row(fields: dict, actor_page_id: Optional[str], ep_num: int,
                   episode_url: str, dry_run: bool = False) -> bool:
    """Push a single STAR row for one episode.

    Field mapping is AO-confirmed 2026-08-10 against the live schema (not
    the handoff's assumed one): Source -> Source URL (episode <link>,
    semantically a URL not free text); Maturity -> Maturity Target ("L2"
    short-form, live option confirmed present); TTPs Summary -> vCISO Hot
    Take; Victim Org -> omitted (noted here, not written -- no live property).
    """
    title = fields.get("topic_concept") or f"Darknet Diaries EP {ep_num}"
    victim_org = fields.get("victim_org")

    if dry_run:
        print(f"   [DRY RUN] would push STAR row:")
        print(f"     Topic/Concept: {title}")
        print(f"     Episode Number: {ep_num}")
        print(f"     Source URL: {episode_url}")
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
    if episode_url:
        properties["Source URL"] = {"url": episode_url}
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
        print(f"❌ Failed to push EP {ep_num} ({title}): {e}")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Darknet Diaries -> STAR ingest pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be pushed, write nothing to Notion")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N new episodes (for testing)")
    parser.add_argument("--episodes", type=str, default=None,
                         help="Comma-separated episode numbers to (re)process directly, bypassing the "
                              "Episode Number cursor -- for retrying specific failed episodes without "
                              "re-running the whole backfill, e.g. --episodes 10,102,104,126")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("⚔️   DARKNET DIARIES -> STAR STRATEGY ENGINE")
    if args.dry_run:
        print("     [DRY RUN -- nothing will be written to Notion]")
    if args.episodes:
        print(f"     [TARGETED RE-RUN -- episodes {args.episodes}, cursor bypassed]")
    print("=" * 65 + "\n")

    actor_cache = _build_actor_cache()
    max_ep = get_existing_max_episode()
    items = fetch_rss()
    if args.episodes:
        target_eps = {int(x.strip()) for x in args.episodes.split(",") if x.strip()}
        new_items = [i for i in items if i["episode_number"] in target_eps]
        found_eps = {i["episode_number"] for i in new_items}
        missing_eps = target_eps - found_eps
        if missing_eps:
            print(f"⚠️  Requested episode(s) not found in feed: {sorted(missing_eps)}\n")
    else:
        new_items = [i for i in items if i["episode_number"] > max_ep]
    if args.limit:
        new_items = sorted(new_items, key=lambda x: x["episode_number"])[:args.limit]

    print(f"Found {len(new_items)} new episode(s) (max existing: EP {max_ep})\n")

    for item in sorted(new_items, key=lambda x: x["episode_number"]):
        ep_num = item["episode_number"]
        print(f"--- EP {ep_num}: {item['title']} ---")

        if not item["transcript_url"]:
            print(f"EP {ep_num}: no transcript available -- skipped\n")
            continue

        try:
            vtt_raw = fetch_vtt(item["transcript_url"])
        except Exception as e:
            print(f"EP {ep_num}: transcript fetch failed ({e}) -- skipped\n")
            continue

        transcript = scrub(strip_vtt(vtt_raw))
        fields = extract_fields_claude(item["title"], transcript)
        if not fields:
            print(f"EP {ep_num}: extraction failed -- skipped\n")
            continue

        actor_page_id = None
        if fields.get("is_threat_actor") and fields.get("threat_actor_name"):
            actor_page_id = resolve_actor(fields["threat_actor_name"], actor_cache, dry_run=args.dry_run)

        ok = push_star_row(fields, actor_page_id, ep_num, item["link"], dry_run=args.dry_run)
        status = "[DRY RUN] would push" if args.dry_run else ("pushed" if ok else "FAILED")
        print(f"EP {ep_num}: {status} -- actor={fields.get('threat_actor_name')}\n")


if __name__ == "__main__":
    main()
