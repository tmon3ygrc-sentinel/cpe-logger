# OPS Handoff — star_threat_ingest.py Dedup Hardening

**Origin:** Cowork session, 2026-08-07. Ported from a real pattern already
verified working in Darksword's `notion_logger_v7.py` (source: user-pasted
directly into this session, not paraphrased from memory).

**Status:** Reviewed diff, not yet applied. AO approved folding both pieces
into one change (see rationale below). Handing to OPS for execution since
this is now write/run work, not analysis.

**Verification before starting:** `git status` on this file's repo first —
confirm clean tree, confirm you're looking at the same `star_threat_ingest.py`
this spec was written against (no drift since 2026-08-07).

---

## Why fold both pieces into one change

Normally: one fold at a time, prove each works before stacking the next.
This case is the exception, not a violation of that rule — both changes
live inside the same ~15-line `is_duplicate()` function. Shipping the retry
wrapper around title-match now, then swapping the match key to a
constructed ID later, means rewriting the same function twice for no
safety benefit. They're not sequentially dependent (B doesn't rely on A
being proven first) — they're co-located. Fold them; each is still
independently testable inside the one change.

---

## Schema decision — RESOLVED 2026-08-08

AO confirmed: **`STAR ID`**, type rich_text, added to the live
`STAR_STRATEGY_DB_V2` (`collection://33a55ed7-4038-802b-9f10-000b98509194`).
Executed via `notion-update-data-source` (`ADD COLUMN "STAR ID" RICH_TEXT`),
verified live via a post-write schema re-fetch — `"STAR ID":{"type":"text"}`
confirmed present, not just taken on the write call's own success response.
No naming/type deviation from this spec's original assumption. Piece 2 is
now unblocked — the field Piece 2's code needs to write to and dedup-check
against exists live. Code itself (Piece 1 + Piece 2 as specced below) is
still unbuilt; this only closes the schema prerequisite.

---

## Piece 1 — Fail-closed dedup + CMMC cache retry

**Problem:** `is_duplicate()` currently does `except Exception: return False`
— any transient Notion API failure (rate limit, timeout) gets silently
read as "not a duplicate, push it." Fail-open. `load_cmmc_cache()` has a
single try/except with no retry — one hiccup and every CMMC relation in
the run fails to resolve with no loud signal why.

**Fix — mirrors v7's `DedupCheckError` / `_notion_query_all` retry
discipline, sized down for this script's lower call volume:**

```python
import time  # add to imports at top of file

class DedupCheckError(RuntimeError):
    """Raised when the STAR DB dedup query cannot be completed after
    retries. Callers must fail CLOSED — treat as unresolved, not as
    'not a duplicate' — never assume absence on a query we couldn't
    actually run."""
    pass


def load_cmmc_cache(retries: int = 3, delay: int = 15):
    """Load CMMC control IDs into memory for relation lookups.
    Retries up to `retries` times on transient failures before giving up."""
    for attempt in range(1, retries + 1):
        print(f"📡 Querying Master Frameworks (attempt {attempt}/{retries}): {CMMC_DB_ID[:8]}...")
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
            return
        except Exception as e:
            if attempt < retries:
                print(f"⏳ CMMC cache error (attempt {attempt}/{retries}) — retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                print(f"❌ CMMC cache failed after {retries} attempts: {e}")
```

---

## Piece 2 — Deterministic STAR ID (replaces title-match dedup)

**Problem:** dedup currently keys off `Topic/Concept` (the free-text title
Claude generates). Any phrasing drift between runs on overlapping content
= false negative on dedup, duplicate pushed.

**Fix — construct an ID from source + date + a Notion-seeded sequence
number, same shape as v7's `_construct_record_id` /
`count_existing_record_ids_with_prefix`. This script only ever ingests from
Barricade Cyber via YouTube, so no multi-source slug map needed — hardcode
`"barricadecyber"`.**

```python
STAR_DB_ID_PREFIX_CACHE: Dict[str, int] = {}  # module-level, add near CMMC_CACHE

def count_existing_star_ids_with_prefix(prefix: str, max_retries: int = 3, delay: float = 2.0) -> int:
    """Counts live STAR DB rows whose STAR ID starts with prefix. Fails
    CLOSED — raises DedupCheckError after retries rather than assuming 0
    (assuming 0 on a failed query would let the sequence restart and
    collide with real existing records)."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            res = notion.data_sources.query(
                STAR_DB_ID,
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
            res = notion.data_sources.query(
                STAR_DB_ID,
                filter={"property": "STAR ID", "rich_text": {"equals": star_id}}
            )
            return len(res.get("results", [])) > 0
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⚠️  Dedup query failed (attempt {attempt}/{max_retries}): {e} — retrying in {delay}s")
                time.sleep(delay)
    raise DedupCheckError(f"Dedup query failed after {max_retries} attempts: {last_exc}")
```

**`ingest()` changes** — construct the ID, use it (not title) for the dedup
check, and write it into the page properties:

```python
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
        "Maturity Target": {"select": {"name": item.get("maturity", "L3 - Repeatable/Managed")}},
        "Horizon":        {"select": {"name": item.get("horizon", "Immediate")}},
        "Ingest Hash":    {"rich_text": [{"text": {"content": fingerprint}}]},
        "Operator":       {"rich_text": [{"text": {"content": OPERATOR_ID}}]},
        "STAR ID":        {"rich_text": [{"text": {"content": star_id}}]},
    }
    # ...rest of function unchanged (cmmc_rels, notion.pages.create, etc.)
```

---

## Post-change verification (required, not optional)

1. `git --no-pager diff star_threat_ingest.py` — confirm the diff matches
   this spec exactly before committing.
2. Dry-run reasoning check: manually trace one call to `construct_star_id()`
   with `STAR_DB_ID_PREFIX_CACHE` empty — confirm it queries Notion once,
   gets a real count back, and produces `barricadecyber-YYYY-MM-DD-01` (or
   correct next seq if same-day records already exist).
3. Live test: run the script once against a real (or test) YouTube URL,
   confirm the new `STAR ID` property lands populated on the created page
   — query it back via Notion, don't trust the script's own success print.
4. Re-run against the *same* URL/content a second time — confirm it now
   hits the dedup path and logs `⏭️  Skipping duplicate`, proving the new
   key actually catches what title-match was missing.
5. `git commit` only after 3–4 pass. Do not push without AO confirmation,
   per standing discipline.

---

## Explicitly not in scope for this handoff

- `generate_fingerprint()`'s SHA-256 hash is unchanged — it's audit-trail
  logging only, never read back or checked against anything. Not a
  dedup/integrity mechanism as currently used; flagged in the original
  Cowork-session review, not touched here.
- No `failed_records.txt`-style persistence layer added — this tool is
  low-volume and interactive (human watches output, decides to re-run),
  unlike v7's unattended `--auto*` paths. Proportionate scope, not an
  oversight.
