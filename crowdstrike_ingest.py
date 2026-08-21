# crowdstrike_ingest.py
# CrowdStrike Adversary Universe -> STAR_STRATEGY_DB_V2 + Threat Actor Registry
# ingest pipeline. See boards/crowdstrike_star_ingest_scope.md for the full
# architecture spec this implements.
#
# Same Notion client / push shape as darknetdiaries_ingest.py, per instruction --
# scrub() and sanitize_multi_select() copied verbatim from that file, not
# reimplemented.
#
# Key differences from Darknet Diaries (per scope doc, confirmed while building):
#   - Transcripts come from disk (Colab Whisper output), not RSS/VTT fetch.
#   - This is a fixed, hardcoded 7-episode one-time backfill (Option A: only the
#     adversary-profile episodes, ALL-CAPS codename in title) -- no RSS polling,
#     no episode-number cursor.
#   - actor_name for resolve_actor() is the AUTHORITATIVE CrowdStrike codename
#     from EPISODES below, not re-derived from Claude's transcript read. This is
#     a deliberate deviation from the Darknet Diaries pattern: DD's own backfill
#     hit a real fragmentation bug from trusting Claude's free-text actor-name
#     extraction -- EP10 created a second, differently-phrased "NSA (National
#     Security Agency)" stub because a re-extraction phrased the name differently
#     than the original run's "NSA". CrowdStrike's adversary-profile format
#     gives an authoritative codename before any Claude call happens; using it
#     avoids that whole failure class.
#   - Dedup is per-episode via Source URL match against STAR_STRATEGY_DB_V2, not
#     "actor already has a STAR relation" as the scope doc literally states.
#     Checked directly, not assumed: SCATTERED SPIDER already exists in the
#     Threat Actor Registry from the Darknet Diaries backfill (canonical_name
#     "scattered-spider", live-queried before writing this file). If the DD
#     backfill's own SCATTERED SPIDER coverage had already linked a STAR
#     relation to that actor row (it happens not to have -- star_strategy_
#     references is null, confirmed live), the scope doc's literal "actor has
#     any STAR relation -> skip" rule would false-positive-skip this CrowdStrike
#     episode entirely, since the *actor* isn't new even though *this episode*
#     is. Source URL is unique per CrowdStrike episode and doesn't care why the
#     actor row exists -- resolve_actor() still finds-and-reuses the actor by
#     canonical_name match (the actual mission requirement), it just isn't also
#     overloaded as the episode-level dedup gate.
#   - classification / attributed_nation_state on new actor-stub creation are
#     populated from Claude's read of CrowdStrike's own attribution, mapped to
#     the LIVE controlled vocab (verified via direct schema fetch before writing
#     this file, not guessed): classification one of [nation-state-apt,
#     ransomware-group, hacktivist, cybercrime-syndicate, insider-threat-pattern,
#     unknown-unattributed]; attributed_nation_state one of [china, russia,
#     north-korea, iran, none, unknown]. Darknet Diaries always wrote the generic
#     "unknown-unattributed"/"unknown" defaults -- CrowdStrike's source material
#     states real attribution (e.g. LABYRINTH CHOLLIMA / FAMOUS CHOLLIMA are
#     DPRK, INDRIK SPIDER is Russian eCrime), so this maps it instead of
#     discarding it, without inventing any new vocab values.
#   - Transcript truncation raised from Darknet Diaries' 15000-char cap to
#     60000 chars -- the largest of the 7 transcripts (indrik_spider.txt,
#     51,591 bytes) still fits whole. DD's cap made sense amortized over a
#     168-episode RSS-scale backfill; this is a 7-episode one-time run where
#     full-transcript coverage (mitigation guidance in these episodes often
#     lands in the closing minutes, confirmed by inspection) matters more than
#     shaving tokens.

import os
import re
import json
import time
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from notion_client import Client
import anthropic

load_dotenv()


# scrub() copied verbatim from darknetdiaries_ingest.py (itself copied verbatim
# from notion_logger_v7.py) -- see that file's header for why this is copied
# rather than imported (notion_logger_v7 has import-time side effects tied to
# an unrelated DB).
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

TRANSCRIPTS_DIR = Path(__file__).parent / "data" / "crowdstrike_transcripts"
TRANSCRIPT_CHAR_LIMIT = 60000

# Same live database-object IDs as darknetdiaries_ingest.py (not the collection://
# data-source IDs the scope doc uses -- notion-client==2.2.1's databases.query()/
# pages.create() reject those; see that file's header for the full finding).
STAR_DB_ID        = "33a55ed7403880e29152d1997bc01f64"
ACTOR_REGISTRY_ID = "c46125e586b3488dbc27518c245cf7fc"

# Fixed 7-episode target list (Option A: adversary-profile episodes only), per
# boards/crowdstrike_star_ingest_scope.md. One-time backfill -- no RSS, no
# cursor. actor_name is the AUTHORITATIVE, title-confirmed canonical name fed
# to resolve_actor() -- see header note on why this isn't re-derived from
# Claude's transcript read.
EPISODES = [
    {
        "actor_key": "labyrinth_chollima",
        "actor_name": "LABYRINTH CHOLLIMA",
        "title": "LABYRINTH CHOLLIMA Evolves into Three Adversaries",
        "audio_url": "https://mcdn.podbean.com/mf/web/wrzb8tvdszumgqd8/Final_EP7yk00.mp3",
    },
    {
        "actor_key": "scattered_spider",
        "actor_name": "SCATTERED SPIDER",
        "title": "The Return of SCATTERED SPIDER",
        "audio_url": "https://mcdn.podbean.com/mf/web/bdusdtnawmssi2fy/Return_of_SCATTERED_SPIDER_Final63n35.mp3",
    },
    {
        "actor_key": "ocular_spider",
        "actor_name": "OCULAR SPIDER",
        "title": "OCULAR SPIDER and the Rise of Ransomware-as-a-Service",
        "audio_url": "https://mcdn.podbean.com/mf/web/ey35s29zttdjz798/OCULAR_SPIDER66kgs.mp3",
    },
    {
        "actor_key": "lunar_spider",
        "actor_name": "LUNAR SPIDER",
        "title": "Meet LUNAR SPIDER: The Inner Workings of an eCrime Adversary",
        "audio_url": "https://mcdn.podbean.com/mf/web/qateem2fachs8ewu/LUNAR_SPIDER_FINAL_AUDIO79qc9.mp3",
    },
    {
        "actor_key": "liminal_panda",
        "actor_name": "LIMINAL PANDA",
        "title": "LIMINAL PANDA and the Implications of Global Telco Targeting",
        "audio_url": "https://mcdn.podbean.com/mf/web/5wdtkeujs7th62aa/CRWDPodcastLIMINALPANDANov2024.mp3",
    },
    {
        "actor_key": "indrik_spider",
        "actor_name": "INDRIK SPIDER",
        "title": "How CrowdStrike Tracked INDRIK SPIDER from Origin to Takedown",
        "audio_url": "https://mcdn.podbean.com/mf/web/icagwmw4iy56m8e6/riverside_jt_copy_of_final_indrik_spider_october_2024_crwd_au_podcast6rz68.mp3",
    },
    {
        "actor_key": "famous_chollima",
        "actor_name": "FAMOUS CHOLLIMA",
        "title": "Hunting the Rogue Insiders Operating for FAMOUS CHOLLIMA",
        "audio_url": "https://mcdn.podbean.com/mf/web/iwwjghhew9yj8zzs/riverside_matt_peters_compressed-audio_crwd_au_podcast_00118p7lg.mp3",
    },
]

# Live controlled vocab for the Threat Actor Registry's classification /
# attributed_nation_state select fields -- verified via direct schema fetch
# before writing this file (collection://320ce6bc-5eb9-488c-8c53-2f17281ac148).
# Claude's extraction is mapped into these sets; anything outside them falls
# back to the safe default rather than writing a novel option and drifting the
# vocab (the exact failure class already logged twice on this board for
# Strategic Pillar / Maturity Target).
VALID_CLASSIFICATIONS = {
    "nation-state-apt", "ransomware-group", "hacktivist",
    "cybercrime-syndicate", "insider-threat-pattern", "unknown-unattributed",
}
VALID_NATION_STATES = {"china", "russia", "north-korea", "iran", "none", "unknown"}

if not NOTION_TOKEN:
    raise ValueError("NOTION_TOKEN missing from .env")

notion = Client(auth=NOTION_TOKEN)


class DedupCheckError(RuntimeError):
    """Raised when a Notion read that gates dedup/actor-cache state can't be
    completed after retries. Fail CLOSED, mirroring darknetdiaries_ingest.py --
    never assume an empty/zero result on a query that actually failed."""
    pass


# ─── STAGE 1 -- TRANSCRIPT LOAD FROM DISK ───────────────────────────────────

def load_transcript(actor_key: str) -> Optional[str]:
    """Read the Colab Whisper transcript for one actor from disk. Returns None
    (not an exception) on a missing file -- lets main() skip that episode and
    keep processing the rest, matching darknetdiaries_ingest.py's per-episode
    skip-on-missing-transcript behavior."""
    path = TRANSCRIPTS_DIR / f"{actor_key}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ─── STAGE 2 -- CLAUDE EXTRACTION ───────────────────────────────────────────

CS_PROMPT = """You are a vCISO-level GRC intelligence analyst extracting structured data from a CrowdStrike Adversary Universe podcast transcript.

Episode title: {title}
Confirmed primary adversary (CrowdStrike's own tracked designation -- do not override or second-guess this): {actor_name}

Analyze the transcript below and return a single JSON object with exactly these fields:

{{
  "topic_concept": "string -- one sentence summary of what this episode is about",
  "actor_classification": "one of: nation-state-apt, ransomware-group, hacktivist, cybercrime-syndicate, insider-threat-pattern, unknown-unattributed -- CrowdStrike's own classification of {actor_name} as described in the episode",
  "attributed_nation_state": "one of: china, russia, north-korea, iran, none, unknown -- the nation-state sponsor/origin CrowdStrike attributes to {actor_name} in the episode; use 'none' for financially-motivated eCrime actors with no state sponsor, 'unknown' only if the episode genuinely doesn't say",
  "actor_aliases": ["array of strings -- other names/tracking IDs for {actor_name} mentioned in the episode (e.g. UNC numbers, other vendors' names)"],
  "attack_techniques": ["array of strings -- MITRE ATT&CK-style technique names or descriptions"],
  "kill_chain_phase": "string -- dominant kill chain phase this episode illustrates (e.g. Initial Access, Exfiltration, Impact)",
  "control_domains": ["array of strings -- GRC control domains this episode is relevant to (e.g. Identity, Supply Chain, Physical Security)"],
  "ttps_summary": "string -- 2-3 sentence narrative summary of {actor_name}'s tactics/techniques/procedures as described in the episode"
}}

Rules:
- {actor_name} is CrowdStrike's own adversary codename, already confirmed as this episode's subject -- do not invent a different actor name.
- actor_classification and attributed_nation_state must be exactly one of the listed options each -- do not invent new values.
- attributed_nation_state should reflect what CrowdStrike's own analysts say in THIS transcript, not outside knowledge.
- Return ONLY the JSON object. No preamble, no markdown fences, no explanation.

Transcript (may be truncated):
{transcript}"""


def extract_fields_claude(title: str, actor_name: str, transcript: str) -> dict:
    """Send transcript to Claude and return the parsed STAR/actor field dict.
    Returns {} on any parse failure -- logs the raw response, never crashes the
    run over one bad episode."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY in .env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = CS_PROMPT.format(
        title=title,
        actor_name=actor_name,
        transcript=transcript[:TRANSCRIPT_CHAR_LIMIT],
    )

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


# ─── STAGE 3 -- resolve_actor() ─────────────────────────────────────────────

def normalize_actor_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_actor_cache(max_retries: int = 3, delay: float = 2.0) -> Dict[str, str]:
    """Pre-load the Threat Actor Registry into a normalized-key -> page_id
    cache: one query covers canonical_name AND every comma-split alias, so an
    actor already in the Registry from ANY prior pipeline (e.g. Darknet
    Diaries) is found and reused rather than duplicated. Copied from
    darknetdiaries_ingest.py -- same fail-CLOSED contract: raises
    DedupCheckError rather than returning an empty cache on a failed query (an
    empty cache on failure would silently create duplicate actor stubs for
    every actor already in the registry, e.g. re-creating SCATTERED SPIDER)."""
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


def resolve_actor(name: str, actor_cache: dict, dry_run: bool = False,
                   classification: Optional[str] = None,
                   nation_state: Optional[str] = None,
                   aliases: Optional[List[str]] = None) -> str:
    """Returns Notion page ID of the actor row, creating a stub if absent.

    Mission-critical requirement: SCATTERED SPIDER (and potentially others of
    the 7 target actors) may already exist in the Threat Actor Registry from
    the Darknet Diaries backfill -- this MUST find and reuse that row, not
    create a duplicate. Live-confirmed before writing this file: SCATTERED
    SPIDER exists as canonical_name "scattered-spider"; normalize_actor_key()
    strips case/spaces/hyphens on both sides, so "SCATTERED SPIDER" (this
    script's authoritative name) and "scattered-spider" (the live row) both
    normalize to "scatteredspider" and match correctly.

    On create only: classification/attributed_nation_state are set from
    Claude's extraction if it returned a value from the live controlled vocab,
    else fall back to the same "unknown-unattributed"/"unknown" defaults
    darknetdiaries_ingest.py always used. On reuse, the existing row's fields
    are left untouched -- no enrichment-on-match in this version (flagged, not
    silently done: if CrowdStrike's episode reveals better attribution for an
    actor DD only stub-created, that's a separate, later pass).
    """
    key = normalize_actor_key(name)
    if key in actor_cache:
        print(f"   ✅ Reusing existing Threat Actor Registry entry for {name} (no duplicate created)")
        return actor_cache[key]

    # Computed before the dry_run branch so dry-run output shows exactly what
    # a live run would set -- AO reviews this, it needs to be real, not a stub.
    safe_classification = classification if classification in VALID_CLASSIFICATIONS else "unknown-unattributed"
    safe_nation_state = nation_state if nation_state in VALID_NATION_STATES else "unknown"

    if dry_run:
        fake_id = f"DRY-RUN-NEW-ACTOR::{name}"
        actor_cache[key] = fake_id
        alias_note = f", aliases: {', '.join(aliases)}" if aliases else ""
        print(f"   [DRY RUN] would create Threat Actor Registry stub: {name} "
              f"(classification={safe_classification}, attributed_nation_state={safe_nation_state}{alias_note})")
        return fake_id

    today = datetime.date.today().isoformat()
    notes = f"CrowdStrike Adversary Universe auto-create, {today}"
    if aliases:
        notes += f" -- aliases mentioned in episode: {', '.join(aliases)}"

    properties = {
        "canonical_name": {"title": [{"text": {"content": name}}]},
        "classification": {"select": {"name": safe_classification}},
        "attributed_nation_state": {"select": {"name": safe_nation_state}},
        "active": {"checkbox": True},
        "analyst_notes": {"rich_text": [{"text": {"content": notes}}]},
    }
    response = notion.pages.create(parent={"database_id": ACTOR_REGISTRY_ID}, properties=properties)
    page_id = response["id"]
    actor_cache[key] = page_id
    print(f"   \U0001f195 Created Threat Actor Registry stub: {name} ({safe_classification}, {safe_nation_state})")
    return page_id


# ─── STAGE 4 -- EPISODE-LEVEL DEDUP (Source URL match) ──────────────────────

def _build_source_url_cache(max_retries: int = 3, delay: float = 2.0) -> set:
    """Pre-load every existing 'Source URL' value already in
    STAR_STRATEGY_DB_V2 into a set. See header note for why this -- not
    "actor already has a STAR relation" -- is the real per-episode dedup key.
    Fails CLOSED like the other cache builders: an empty set on a failed query
    would look identical to "nothing pushed yet" and re-push everything."""
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


# ─── STAGE 5 -- STAR ROW PUSH ────────────────────────────────────────────────

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


def push_star_row(fields: dict, actor_page_id: Optional[str], episode: dict,
                   dry_run: bool = False) -> bool:
    """Push a single STAR row for one CrowdStrike episode.

    Field mapping matches darknetdiaries_ingest.py's live-confirmed schema
    (Source -> Source URL, Maturity -> Maturity Target, TTPs Summary ->
    vCISO Hot Take) -- no Episode Number field, CrowdStrike has none.
    """
    title = fields.get("topic_concept") or episode["title"]
    audio_url = episode["audio_url"]

    if dry_run:
        print(f"   [DRY RUN] would push STAR row:")
        print(f"     Topic/Concept: {title}")
        print(f"     Source URL: {audio_url}")
        print(f"     Threat Actors: {[actor_page_id] if actor_page_id else []}")
        print(f"     attack_techniques: {fields.get('attack_techniques', [])}")
        print(f"     kill_chain_phase: {fields.get('kill_chain_phase')}")
        print(f"     control_domains: {fields.get('control_domains', [])}")
        print(f"     Maturity Target: L2")
        print(f"     vCISO Hot Take: {fields.get('ttps_summary', '')[:200]}")
        return True

    properties = {
        "Topic/Concept":   {"title": [{"text": {"content": title[:2000]}}]},
        "Maturity Target": {"select": {"name": "L2"}},
        "Source URL":      {"url": audio_url},
    }
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
        print(f"❌ Failed to push {episode['actor_key']} ({title}): {e}")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CrowdStrike Adversary Universe -> STAR ingest pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be pushed, write nothing to Notion")
    parser.add_argument("--episodes", type=str, default=None,
                         help="Comma-separated actor_keys to (re)process directly, e.g. "
                              "--episodes scattered_spider,indrik_spider -- default is all 7")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("\U0001f47e  CROWDSTRIKE ADVERSARY UNIVERSE -> STAR STRATEGY ENGINE")
    if args.dry_run:
        print("     [DRY RUN -- nothing will be written to Notion]")
    print("=" * 65 + "\n")

    if args.episodes:
        target_keys = {k.strip() for k in args.episodes.split(",") if k.strip()}
        episodes = [e for e in EPISODES if e["actor_key"] in target_keys]
        missing = target_keys - {e["actor_key"] for e in episodes}
        if missing:
            print(f"⚠️  Requested actor_key(s) not found in EPISODES: {sorted(missing)}\n")
    else:
        episodes = EPISODES

    actor_cache = _build_actor_cache()
    source_url_cache = _build_source_url_cache()

    print(f"Processing {len(episodes)} episode(s)\n")

    for episode in episodes:
        actor_key = episode["actor_key"]
        actor_name = episode["actor_name"]
        print(f"--- {actor_key}: {episode['title']} ---")

        if episode["audio_url"] in source_url_cache:
            print(f"{actor_key}: Source URL already present in STAR_STRATEGY_DB_V2 -- already pushed, skipped\n")
            continue

        transcript_raw = load_transcript(actor_key)
        if transcript_raw is None:
            print(f"{actor_key}: no transcript file on disk ({actor_key}.txt) -- skipped\n")
            continue

        transcript = scrub(transcript_raw)
        fields = extract_fields_claude(episode["title"], actor_name, transcript)
        if not fields:
            print(f"{actor_key}: extraction failed -- skipped\n")
            continue

        actor_page_id = resolve_actor(
            actor_name, actor_cache, dry_run=args.dry_run,
            classification=fields.get("actor_classification"),
            nation_state=fields.get("attributed_nation_state"),
            aliases=fields.get("actor_aliases"),
        )

        ok = push_star_row(fields, actor_page_id, episode, dry_run=args.dry_run)
        status = "[DRY RUN] would push" if args.dry_run else ("pushed" if ok else "FAILED")
        print(f"{actor_key}: {status} -- actor={actor_name}\n")


if __name__ == "__main__":
    main()
