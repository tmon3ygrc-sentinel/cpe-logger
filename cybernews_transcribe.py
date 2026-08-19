"""
cybernews_transcribe.py
Cybernews podcast → Whisper transcription batch script

Phase 1 of the Cybernews 88-episode backfill pipeline.
Downloads all episodes from the RSS feed and transcribes them locally
using faster-whisper (large-v2, CUDA) on the RTX 3070.

Checkpoint: transcript file existence. Kill and restart safely at any point —
completed episodes are skipped automatically.

Output:
  data/cybernews_transcripts/manifest.json       — episode metadata for ingest script
  data/cybernews_transcripts/{guid}.txt          — one transcript per episode

Usage:
  python cybernews_transcribe.py                 # full run
  python cybernews_transcribe.py --dry-run       # parse feed + write manifest, no download
  python cybernews_transcribe.py --limit N       # process only N episodes (spot-check)
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────

RSS_URL         = "https://anchor.fm/s/d69ab560/podcast/rss"
TRANSCRIPT_DIR  = Path(r"C:\Work\GRC\darksword\data\cybernews_transcripts")
MANIFEST_PATH   = TRANSCRIPT_DIR / "manifest.json"
WHISPER_MODEL   = "large-v2"
MIN_VALID_BYTES = 500   # transcript smaller than this = treat as empty/failed

# ── Namespaces ────────────────────────────────────────────────────────────────

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "atom":   "http://www.w3.org/2005/Atom",
}


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── RSS parsing ───────────────────────────────────────────────────────────────

def fetch_rss() -> list[dict]:
    """Fetch and parse RSS feed. Returns list of episode dicts, oldest-first."""
    log(f"Fetching RSS: {RSS_URL}")
    with urllib.request.urlopen(RSS_URL, timeout=30) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("No <channel> element found in RSS")

    items = channel.findall("item")
    log(f"Found {len(items)} items in feed")

    episodes = []
    for item in items:
        guid_el    = item.find("guid")
        title_el   = item.find("title")
        link_el    = item.find("link")
        pubdate_el = item.find("pubDate")
        enc_el     = item.find("enclosure")
        ep_el      = item.find("itunes:episode", NS)
        dur_el     = item.find("itunes:duration", NS)

        if enc_el is None:
            log(f"  ⚠ No enclosure: {_text(title_el)} — skipping")
            continue

        guid = (_text(guid_el) or "").strip()
        if not guid:
            log(f"  ⚠ No GUID: {_text(title_el)} — skipping")
            continue

        episodes.append({
            "guid":             guid,
            "episode_number":   _safe_int(_text(ep_el)),
            "title":            _text(title_el),
            "audio_url":        enc_el.attrib.get("url", ""),
            "pub_date":         _text(pubdate_el),
            "duration_seconds": _parse_duration(_text(dur_el)),
            "link":             _text(link_el),
        })

    # Oldest-first so checkpoint progress reads forward
    episodes.sort(key=lambda e: e["pub_date"])
    log(f"Parsed {len(episodes)} episodes with enclosures")
    return episodes


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _safe_int(s: str):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_duration(s: str) -> int:
    """HH:MM:SS or MM:SS or raw seconds → int seconds."""
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


# ── Manifest ──────────────────────────────────────────────────────────────────

def write_manifest(episodes: list[dict]) -> None:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)
    log(f"Manifest → {MANIFEST_PATH} ({len(episodes)} episodes)")


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Checkpoint ────────────────────────────────────────────────────────────────

def transcript_path(guid: str) -> Path:
    safe = re.sub(r"[^\w\-]", "_", guid)
    return TRANSCRIPT_DIR / f"{safe}.txt"


def is_done(guid: str) -> bool:
    p = transcript_path(guid)
    return p.exists() and p.stat().st_size >= MIN_VALID_BYTES


# ── Download ──────────────────────────────────────────────────────────────────

def download_audio(url: str, dest: str) -> None:
    log(f"  Downloading audio...")
    start = time.time()

    def _report(block_num, block_size, total_size):
        if total_size > 0 and block_num % 100 == 0:
            pct = min(100, block_num * block_size * 100 // total_size)
            sys.stdout.write(f"\r  {pct}%")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=_report)
    sys.stdout.write("\n")
    size_mb = os.path.getsize(dest) / 1_048_576
    log(f"  Downloaded {size_mb:.1f} MB in {time.time() - start:.0f}s")


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe(audio_path: str, duration_seconds: int = 0) -> str:
    """
    Transcribe with faster-whisper large-v2 on CUDA.
    Logs progress every ~15 minutes of audio.
    """
    from faster_whisper import WhisperModel

    log(f"  Loading Whisper {WHISPER_MODEL} (CUDA)...")
    model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")

    dur_display = f"{duration_seconds // 60}m audio" if duration_seconds else "unknown duration"
    log(f"  Transcribing ({dur_display})...")

    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        language="en",
        vad_filter=True,
    )

    texts = []
    last_log_time = 0
    LOG_INTERVAL = 900  # log progress every 15 min of audio

    for segment in segments:
        texts.append(segment.text)
        if segment.end - last_log_time >= LOG_INTERVAL:
            log(f"  ... {segment.end / 60:.0f}m processed")
            last_log_time = segment.end

    full_text = " ".join(texts).strip()
    log(f"  Transcript: {len(full_text):,} chars")
    return full_text


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cybernews batch transcription")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Fetch feed + write manifest, no download/transcription")
    parser.add_argument("--limit",         type=int, default=None,
                        help="Process only N episodes (spot-check)")
    parser.add_argument("--skip-manifest", action="store_true",
                        help="Reuse existing manifest.json (skip RSS fetch)")
    args = parser.parse_args()

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: RSS + manifest
    if args.skip_manifest:
        episodes = load_manifest()
        log(f"Loaded manifest: {len(episodes)} episodes")
    else:
        episodes = fetch_rss()
        write_manifest(episodes)

    if args.limit:
        episodes = episodes[:args.limit]
        log(f"Limit: {args.limit} episode(s)")

    # Dry-run: show status table and exit
    if args.dry_run:
        log("\nDry-run — episode status:")
        total_dur = 0
        for ep in episodes:
            status = "✓" if is_done(ep["guid"]) else "○"
            dur = ep["duration_seconds"]
            total_dur += dur
            log(f"  [{status}] EP{str(ep['episode_number'] or '?'):>3} | "
                f"{dur // 60:>3}m | {ep['title'][:55]}")
        log(f"\nTotal audio: {total_dur // 3600}h {(total_dur % 3600) // 60}m")
        log("Dry-run complete. No downloads.")
        return

    # Step 2: Transcribe
    total   = len(episodes)
    skipped = 0
    failed  = []

    log(f"\n{'='*60}")
    log(f"Transcription run: {total} episodes")
    already_done = sum(1 for ep in episodes if is_done(ep["guid"]))
    log(f"Already done: {already_done} | Remaining: {total - already_done}")
    log(f"{'='*60}\n")

    for idx, ep in enumerate(episodes, 1):
        guid  = ep["guid"]
        title = ep["title"]
        ep_num = ep.get("episode_number") or "?"
        dur   = ep["duration_seconds"]
        dur_s = f"{dur // 60}m" if dur else "?"

        log(f"[{idx}/{total}] EP{ep_num} — {title[:55]} ({dur_s})")

        if is_done(guid):
            log(f"  ✓ Done — skip")
            skipped += 1
            continue

        # Download
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            download_audio(ep["audio_url"], tmp_path)
        except Exception as e:
            log(f"  ✗ Download failed: {e}")
            failed.append({"ep": ep_num, "title": title, "error": str(e)})
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            continue

        # Transcribe
        try:
            text = transcribe(tmp_path, dur)
        except Exception as e:
            log(f"  ✗ Transcription failed: {e}")
            failed.append({"ep": ep_num, "title": title, "error": str(e)})
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            continue
        finally:
            # Always delete MP3 temp file — conserve disk
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # Save transcript
        out = transcript_path(guid)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        log(f"  ✓ → {out.name}")

    # Summary
    log(f"\n{'='*60}")
    log(f"Run complete")
    log(f"  Total:   {total}")
    log(f"  Skipped: {skipped} (already done)")
    log(f"  New:     {total - skipped - len(failed)}")
    log(f"  Failed:  {len(failed)}")
    if failed:
        log("\nFailed:")
        for f in failed:
            log(f"  EP{f['ep']} — {f['title'][:50]}: {f['error']}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
