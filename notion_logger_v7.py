"""
⚔️  DARKSWORD — GRC Intelligence Platform V7.0
Autonomous Intelligence Pipeline
Show Notes → Claude Analysis → Notion

MODES:
  Live Mode  — Full autonomous pipeline (requires ANTHROPIC_API_KEY)
  Test Mode  — Bypasses API entirely, uses saved governance_input.txt
               Run 100 times for $0.00 until pipeline is bulletproof.

CHANGELOG v7.0:
  + get_show_notes() — fetches cyberthreatbrief.simplycyber.io directly
    Bypasses YouTube network block entirely. Zero yt-dlp, zero Whisper,
    zero FFmpeg. Date-addressable: backfill any day with YYYY-MM-DD.
  + analyze_with_claude() — implemented (was a stub in V6)
  + write_governance_file() — implemented (was a stub in V6)
  + load_mock_data() — implemented (was a stub in V6)
  + Choice 1 (Autonomous Pipeline) now fully operational for Simply Cyber
  + Model: claude-sonnet-4-6
  + get_transcript() retained for future non-blocked sources

KNOWN LIMITATIONS:
  - get_transcript() (Whisper/yt-dlp) still blocked for Simply Cyber at
    network/IP level. Use get_show_notes() for all Simply Cyber content.
  - Show notes page must be published before pipeline runs. Early AM runs
    may need to wait ~30 min after episode drops.
"""

import os
import re
import sys
import time
import anthropic
import feedparser
import requests
import pyperclip
from datetime import date
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
from bs4 import BeautifulSoup
from notion_client import Client
from dotenv import load_dotenv

# ===================================================================
# 1. CONFIGURATION & MODE DETECTION
# ===================================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

# Run with: python notion_logger_v7.py --test
# Run with: python notion_logger_v7.py --auto                          (non-interactive, for Task Scheduler)
# Run with: python notion_logger_v7.py --auto-otx                     (non-interactive OTX pipeline only)
# Run with: python notion_logger_v7.py --auto-otx --lookback-hours 48 (backfill missed runs, max 72)
# Run with: python notion_logger_v7.py --auto-barricade               (non-interactive Barricade Cyber pipeline)
# Run with: python notion_logger_v7.py --push-reviewed                (push AO-reviewed audio-ingest records; archives pending file after)
# Run with: python notion_logger_v7.py --push-corrections             (interactive: apply AO-reviewed field-level corrections to already-live records; record_corrections.txt)
TEST_MODE          = "--test"           in sys.argv
AUTO_MODE          = "--auto"           in sys.argv
AUTO_OTX_MODE      = "--auto-otx"      in sys.argv
AUTO_BARRICADE_MODE = "--auto-barricade" in sys.argv
PUSH_REVIEWED_MODE = "--push-reviewed" in sys.argv
PUSH_CORRECTIONS_MODE = "--push-corrections" in sys.argv

def _parse_lookback_hours() -> int:
    for i, arg in enumerate(sys.argv):
        if arg == "--lookback-hours" and i + 1 < len(sys.argv):
            try:
                val = int(sys.argv[i + 1])
            except ValueError:
                raise ValueError(f"❌ --lookback-hours must be an integer, got: {sys.argv[i + 1]}")
            if val < 1 or val > 72:
                raise ValueError(f"❌ --lookback-hours must be between 1 and 72, got: {val}")
            return val
    return 24

LOOKBACK_HOURS = _parse_lookback_hours()

if TEST_MODE and AUTO_MODE:
    raise ValueError("❌ --test and --auto are mutually exclusive.")
if TEST_MODE and AUTO_OTX_MODE:
    raise ValueError("❌ --test and --auto-otx are mutually exclusive.")
if TEST_MODE and AUTO_BARRICADE_MODE:
    raise ValueError("❌ --test and --auto-barricade are mutually exclusive.")
if AUTO_MODE and AUTO_OTX_MODE:
    raise ValueError("❌ --auto and --auto-otx are mutually exclusive.")
if AUTO_MODE and AUTO_BARRICADE_MODE:
    raise ValueError("❌ --auto and --auto-barricade are mutually exclusive.")
if AUTO_OTX_MODE and AUTO_BARRICADE_MODE:
    raise ValueError("❌ --auto-otx and --auto-barricade are mutually exclusive.")
if TEST_MODE and PUSH_REVIEWED_MODE:
    raise ValueError("❌ --test and --push-reviewed are mutually exclusive.")
if AUTO_MODE and PUSH_REVIEWED_MODE:
    raise ValueError("❌ --auto and --push-reviewed are mutually exclusive.")
if AUTO_OTX_MODE and PUSH_REVIEWED_MODE:
    raise ValueError("❌ --auto-otx and --push-reviewed are mutually exclusive.")
if AUTO_BARRICADE_MODE and PUSH_REVIEWED_MODE:
    raise ValueError("❌ --auto-barricade and --push-reviewed are mutually exclusive.")
if TEST_MODE and PUSH_CORRECTIONS_MODE:
    raise ValueError("❌ --test and --push-corrections are mutually exclusive.")
if AUTO_MODE and PUSH_CORRECTIONS_MODE:
    raise ValueError("❌ --auto and --push-corrections are mutually exclusive.")
if AUTO_OTX_MODE and PUSH_CORRECTIONS_MODE:
    raise ValueError("❌ --auto-otx and --push-corrections are mutually exclusive.")
if AUTO_BARRICADE_MODE and PUSH_CORRECTIONS_MODE:
    raise ValueError("❌ --auto-barricade and --push-corrections are mutually exclusive.")
if PUSH_REVIEWED_MODE and PUSH_CORRECTIONS_MODE:
    raise ValueError("❌ --push-reviewed and --push-corrections are mutually exclusive.")

NOTION_TOKEN      = os.getenv("NOTION_TOKEN")
DATABASE_ID       = os.getenv("DATABASE_ID")
CMMC_DB_ID        = os.getenv("CMMC_DATABASE_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("❌ Missing NOTION_TOKEN or DATABASE_ID in .env")

if not TEST_MODE and not ANTHROPIC_API_KEY:
    raise ValueError(
        "❌ Missing ANTHROPIC_API_KEY in .env\n"
        "   💡 Free debug mode: python notion_logger_v7.py --test"
    )

notion = Client(auth=NOTION_TOKEN)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if not TEST_MODE else None

if TEST_MODE:
    print("⚠️  TEST MODE ACTIVE — Anthropic API will NOT be called. $0.00 cost.")
else:
    print("✅ Notion + Claude clients initialized")

# ===================================================================
# 2. CACHES
# ===================================================================
LEARNING_CACHE = {
    "Week 1":  os.getenv("LEARNING_WEEK_1",  ""),
    "Week 2":  os.getenv("LEARNING_WEEK_2",  ""),
    "Week 3":  os.getenv("LEARNING_WEEK_3",  ""),
    "Week 5":  os.getenv("LEARNING_WEEK_5",  ""),
    "Week 6":  os.getenv("LEARNING_WEEK_6",  ""),
    "Week 7":  os.getenv("LEARNING_WEEK_7",  ""),
    "Week 8":  os.getenv("LEARNING_WEEK_8",  ""),
    "Week 10": os.getenv("LEARNING_WEEK_10", ""),
    "Week 11": os.getenv("LEARNING_WEEK_11", ""),
    "Week 12": os.getenv("LEARNING_WEEK_12", ""),
    "Week 13": os.getenv("LEARNING_WEEK_13", ""),
    "Week 14": os.getenv("LEARNING_WEEK_14", ""),
    "Week 15": os.getenv("LEARNING_WEEK_15", ""),
    "Week 17": os.getenv("LEARNING_WEEK_17", ""),
    "Week 18": os.getenv("LEARNING_WEEK_18", ""),
    "Week 19": os.getenv("LEARNING_WEEK_19", ""),
    "Week 20": os.getenv("LEARNING_WEEK_20", ""),
    "Week 21": os.getenv("LEARNING_WEEK_21", ""),
    "Week 23": os.getenv("LEARNING_WEEK_23", ""),
    "Week 24": os.getenv("LEARNING_WEEK_24", ""),
    "Week 25": os.getenv("LEARNING_WEEK_25", ""),
    "Week 26": os.getenv("LEARNING_WEEK_26", ""),
    "Week 27": os.getenv("LEARNING_WEEK_27", ""),
    "Week 28": os.getenv("LEARNING_WEEK_28", ""),
    "Week 29": os.getenv("LEARNING_WEEK_29", ""),
    "Week 30": os.getenv("LEARNING_WEEK_30", ""),
    "Week 33": os.getenv("LEARNING_WEEK_33", ""),
    "Week 35": os.getenv("LEARNING_WEEK_35", ""),
    "Week 36": os.getenv("LEARNING_WEEK_36", ""),
}

DOMAIN_TO_WEEKS = {
    "Incident Response (IR)":                    ["Week 23"],
    "Supply Chain Risk Management (SR)":         ["Week 19", "Week 29"],
    "Risk Assessment (RA)":                      ["Week 18", "Week 20"],
    "Access Control (AC)":                       ["Week 13"],
    "Identification and Authentication (IA)":    ["Week 13"],
    "Configuration Management (CM)":             ["Week 12"],
    "System Integrity (SI)":                     ["Week 17"],
    "System and Communications Protection (SC)": ["Week 17"],
    "Security Awareness and Training (AT)":      ["Week 5"],
    "Logging and Monitoring (AU)":               ["Week 27", "Week 28"],
}

CATEGORY_TO_WEEKS = {
    "regulatory":            ["Week 25"],
    "advisory":              ["Week 26"],
    "supply-chain":          ["Week 19", "Week 29"],
    "incident":              ["Week 23"],
    "ransomware":            ["Week 23"],
    "campaign":              ["Week 18"],
    "vulnerability":         ["Week 20", "Week 21"],
    "malware":               ["Week 19"],
    "breach":                ["Week 28"],
    "law-enforcement":       ["Week 25"],
    "ai-risk":               ["Week 17"],
    "phishing":              ["Week 23"],
    "identity-intelligence": ["Week 13"],
}

CMMC_CACHE: Dict[str, list] = defaultdict(list)  # nist_ref → [(maturity, page_id), ...]
CMMC_MISSES: List[str] = []

# ===================================================================
# 3. FIELD MAPPINGS
# ===================================================================
SELECT_FIELDS = {
    "content_category", "exploit_maturity", "source", "story_type",
    "response_urgency", "asset_criticality", "active_exploitation",
    "confidence", "cisa_kev", "intel_type", "source_show"
}

MULTI_SELECT_FIELDS = {
    "attack_tactic",
    "impacted_identity_provider",
    "content_type", "cpe_category", "kill_chain_phase",
    "attack_techniques", "target_sector",
    "threat_actor", "priority_level", "intel_category", "control_domains",
    "dfir_phase", "investigation_type"
}

RICH_TEXT_FIELDS = {"key_takeaways", "executive_summary", "operational_relevance", "record_id", "tags", "identity_impact", "detection_opportunities"}
DATE_FIELDS      = {"intel_date", "intel_timestamp"}
NUMBER_FIELDS    = {"risk_severity_score"}

SKIP_FIELDS = {
    "url", "title", "cpe_credits",
    "cmmc_mapping", "learning_phase",
    "GRC_Learning_Plan_All_Phases",
    "Master Frameworks(CMMC 2.0 / NIST 800-171)"
}

# ===================================================================
# 4. ANALYST SYSTEM PROMPT
# ===================================================================
ANALYST_PROMPT = """
### MISSION OBJECTIVE
You are a Senior Intelligence Analyst for CPE logging.
Convert security transcripts into COMPLETE, Parser-Ready Intel Records with vCISO-grade intelligence value.
You MUST populate ALL fields. Use "Unknown" or "None" if data is unavailable.
DO NOT use markdown formatting in the output.
DO NOT use bullet points in field values.
DO NOT omit any fields.
Only use control IDs that exist in CMMC 2.0 / NIST 800-171 Rev 2.
Do NOT invent or approximate control IDs. If unsure, use "None".

### OUTPUT FORMAT RULES
- Format: fieldname:: value
- Multi-value: value1, value2 (no bullet points)
- Boundaries: ===INTEL_RECORD_START=== and ===INTEL_RECORD_END===
- NO markdown, NO conversational filler, NO bolding in values.

### PROCESSING GATE
If the message ends with: [END OF PART 1 - DO NOT ANALYZE YET]
Respond ONLY with: "Part received. Awaiting remaining transcript."
Do not perform analysis until you receive: [END OF TRANSCRIPT - BEGIN ANALYSIS]

### REQUIRED OUTPUT SCHEMA
===INTEL_RECORD_START===
record_id::
intel_date::
intel_timestamp::
date_watched::
source::
source_show::
url::
title::
cpe_category::
cpe_credits::
content_type::
content_category::
threat_actor::
target_sector::
intel_category::
cisa_kev::
active_exploitation::
exploit_maturity::
kill_chain_phase::
attack_tactic::
attack_techniques::
risk_severity_score::
confidence::
priority_level::
asset_criticality::
identity_impact::
intel_type::
response_urgency::
identity_impact::
detection_opportunities::
control_domains::
Master Frameworks(CMMC 2.0 / NIST 800-171)::
GRC_Learning_Plan_All_Phases::
tags::
key_takeaways::
story_type::
operational_relevance::
executive_summary::
dfir_phase::
investigation_type::
impacted_identity_provider::
===INTEL_RECORD_END===

### FIELD DEFINITIONS (STRICT)
- **record_id**: source-epNNNN-YYYY-MM-DD-## (e.g., simplycyber-ep1075-2026-02-24-01)
- **intel_date**: Date of the threat/event (YYYY-MM-DD).
- **intel_timestamp**: ISO 8601. If time unknown, DEFAULT TO T14:00:00Z.
- **date_watched**: Date content was consumed (YYYY-MM-DD).
- **source**: Full name of source channel (e.g., Simply Cyber).
- **source_show**: Use ONLY these canonical values — "Simply Cyber Daily Threat Brief" for Simply Cyber content, "AlienVault OTX" for OTX pulses, "Barricade Cyber" for Barricade content.
- **url**: Direct link to the source/video.
- **title**: Concise, professional title of the specific threat event.
- **cpe_category**: Always "Technical" unless specified.
- **cpe_credits**: Always "0.5" per record.
- **content_type**: Always "Podcast/Video".
- **intel_category**: malware, vulnerability, campaign, advisory, breach, tooling, threat-actor, governance, risk-management, identity-intelligence, strategic-intelligence, dfir, compliance. Select closest match(es). Do NOT invent new categories.
- **kill_chain_phase**: reconnaissance, weaponization, delivery, exploitation, installation, command-and-control, actions-on-objectives.
- **attack_tactic**: MITRE ATT&CK tactics (lowercase, hyphenated).
- **attack_techniques**: MITRE ATT&CK technique IDs (UPPERCASE, e.g., T1190, T1059).
- **intel_type**: tactical, strategic, or operational.
- **asset_criticality**: tier-zero, high, medium, low.
- **identity_impact**: Write 1-2 analyst sentences describing which identity types are impacted and how. Focus on blast radius and authentication context.
- **response_urgency**: immediate-action, scheduled, monitor, strategic-review.
- **cisa_kev**: Explicitly "yes", "no", or "unknown".
- **confidence**: High, Medium, or Low.
- **priority_level**: Critical, High, Medium, or Low.
- **exploit_maturity**: poc, functional, weaponized, living-off-the-land, automated, theoretical, unknown.
- **risk_severity_score**: 0-10.
- **detection_opportunities**: Short hyphenated tags only, max 5 words each, comma-separated. NO full sentences. Examples: anomalous-powershell-execution, mfa-device-enrollment, lateral-movement-smb, dns-beaconing-detected, unsigned-driver-load. Format: lowercase-hyphenated-slug. Max 6 tags per record.
- **control_domains**: Access Control (AC), Identification and Authentication (IA), Endpoint Security, Malware Protection, Logging and Monitoring (AU), Incident Response (IR), Threat Intelligence, Configuration Management (CM), Cloud Security, API Security, Data Protection, Privacy and Compliance, Security Awareness and Training (AT), Risk Assessment (RA), Supply Chain Risk Management (SR), System Integrity (SI). Use full names exactly as shown.
- **Master Frameworks(CMMC 2.0 / NIST 800-171)**: CMMC 2.0 Control IDs in exact format XX.L#-#.##.# (e.g., AC.L1-3.1.1, SI.L2-3.14.1, IR.L2-3.6.1). Comma-separated. Use "None" if no clear mapping.
  CRITICAL EXCEPTIONS — these are frequent errors:
  - IA 3.5.1 and 3.5.2: these originate from FAR 52.204-21 and are Level 1 practices in the DoD CMMC model. ALWAYS write IA.L1-3.5.1 and IA.L1-3.5.2. NEVER write IA.L2-3.5.1 or IA.L2-3.5.2 — those IDs do not exist in the official CMMC model.
  - SI 3.14.2: corrected to Level 1 per Master Frameworks DB Defect D (2026-07-02) — the SI family has no Level 2 requirement at this ref. ALWAYS write SI.L1-3.14.2. NEVER write SI.L2-3.14.2.
  - SR controls: valid requirement ranges are 3.15.x and 3.24.x ONLY (e.g., SR.L2-3.15.1, SR.L2-3.24.1). SR.L2-3.17.x does not exist — do NOT output any SR.3.17.x ID. Use "None" if no valid SR control applies.
- **GRC_Learning_Plan_All_Phases**: Map to the most relevant week: "Week ## - [title]". Options: Week 25 - Developing security policies, Week 26 - Building compliance programs, Week 27 - Risk management frameworks. Leave blank if no match.
- **identity_impact**: Who is impacted (comma-separated). Values: workforce-accounts, administrative-roles, system-administrators, security-operations, service-accounts, non-human-identities, executive-accounts, third-party-vendors, none, unknown.
- **tags**: ALL MITRE IDs (lowercase) AND descriptive keywords (lowercase-hyphenated).
- **story_type**: MUST be exactly one of: incident, vulnerability, advisory, strategic, legal-regulatory.
- **threat_actor**: Name(s) of the threat actor(s) or group(s), comma-separated if multiple. Proper noun only, exactly as commonly reported (e.g., "LockBit", "Salt Typhoon", "ShinyHunters") — one name per comma-separated entry. If attribution is not to a named actor, use exactly one of: unknown, unattributed, nation-state, state-sponsored, e-crime, insider, hacktivist. Do NOT add parenthetical commentary or confidence/sourcing qualifiers to this field (no "(unconfirmed)", "(suspected)", "(sanctioned)", "(multiple subscribers)", etc.) — put any attribution confidence, sourcing, or legal/sanctions caveats in key_takeaways instead.
- **target_sector**: Industry/sector(s) targeted, comma-separated if multiple. Values: healthcare, financial-services, government, education, energy, critical-infrastructure, technology, telecommunications, retail, manufacturing, defense, legal, media, non-profit, consumer, unknown. Do NOT add parenthetical commentary — use "unknown" if unclear.
- **key_takeaways**: 2-4 analyst sentences (plain text, no bullet characters) capturing the most actionable insights. Include any attribution confidence, sourcing, or qualifying caveats here (e.g., unconfirmed attribution, sanctions status, subscriber/victim counts) rather than embedding them in threat_actor or target_sector.
- **executive_summary**: Exactly 3 sentences.
- **dfir_phase**: initial-triage, containment, eradication, recovery. Use "None" if not active incident.
- **investigation_type**: threat-hunt, incident-response, vulnerability-assessment, compliance-review. Use "None" if not applicable.
- **content_category**: Threat Intelligence, AI Governance / Privacy Law, Technical, Management, DFIR, Compliance, Strategic, Legal-Regulatory. Select closest match. Do NOT invent new categories.

### INTELLIGENCE ANALYSIS GUIDELINES
1. Be Intelligence-Driven: Focus on threats, vulnerabilities, and defensive opportunities.
2. Use Analyst Judgment: Infer reasonable values when data is partial.
3. Prioritize Detection: Always think "how would a SOC catch this?"
4. Map to Frameworks: Always include MITRE ATT&CK mappings when possible.
5. Score Consistently: Use the defined 0-10 scale strictly.
6. Identity-First: Modern attacks target identity — always assess identity_impact.
7. CMMC Mapping: Always attempt to map to CMMC 2.0 controls. Priority: AC, IA, SI, AU, SC.

### STORY IDENTIFICATION RULES (MANDATORY)
A record MUST be created if ANY of the following are present:
- Named organization with security impact
- Mention of breach, data exposure, ransomware, or compromise
- Mention of vulnerability or active exploitation
- Mention of threat actor activity or campaign
- Security advisory tied to a specific technology or control failure
- Credentials, admin accounts, tenant access, or authentication mentioned
If uncertain, CREATE the record and mark confidence:: Low.

### EXTRACTION BIAS RULE
Prefer over-extraction. Missing a story is a failure.

### PRE-OUTPUT VALIDATION STEP (MANDATORY)
Before finalizing output:
1. Enumerate total stories identified
2. Verify one complete record exists per story
3. Confirm no qualifying story was omitted
4. If mismatch — regenerate before output
"""

# ===================================================================
# 4b. OTX ANALYST PROMPT (tuned for AlienVault pulse metadata)
# ===================================================================
OTX_ANALYST_PROMPT = (
    ANALYST_PROMPT
    .replace(
        'content_type::\ncontent_category::\n',
        'content_type:: Threat Intelligence Feed\ncontent_category:: Threat Intelligence\n'
    )
    .replace(
        '- **content_type**: Always "Podcast/Video".',
        '- **content_type**: ALWAYS "Threat Intelligence Feed" for OTX pulses. Do NOT use "Podcast/Video".'
    )
    .replace(
        '- **content_category**: Threat Intelligence, AI Governance / Privacy Law, Technical, Management, DFIR, Compliance, Strategic, Legal-Regulatory. Select closest match. Do NOT invent new categories.',
        '- **content_category**: For OTX pulses, default to "Threat Intelligence". Override only if content is clearly advisory, compliance, or strategic. Do NOT leave blank.'
    )
    .replace(
        '- **investigation_type**:',
        '- **impacted_identity_provider**: Identity provider targeted by this threat. ALWAYS populate. Values (comma-separated): on-prem-ad, entra-id, okta, google-workspace, mfa-provider, aws-iam, none, unknown. Use "unknown" if unclear. Do NOT leave blank.\n- **investigation_type**:'
    )
)

# ===================================================================
# 5. UTILITY FUNCTIONS
# ===================================================================

def to_text(val: str) -> list:
    """Builds a Notion rich_text block from a string."""
    return [{"text": {"content": str(val)[:2000]}}] if val else []

def to_select(val: str) -> dict:
    """Builds a Notion select block from a string."""
    return {"name": str(val).strip()} if val else None

def split_top_level(val: str) -> list:
    """
    Splits a string on commas at paren-depth 0 only — a comma inside an
    open (...) is part of the enclosing token, not a delimiter. Unbalanced
    parens degrade safely: depth never goes below 0, and an unclosed "("
    just keeps the rest of the string in the current token instead of
    splitting it further.
    """
    items = []
    current = []
    depth = 0
    for ch in val:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    items.append("".join(current))
    return items

def to_multi(val: str) -> list:
    """Splits a string into Notion multi_select blocks on top-level commas only."""
    items = [x.strip() for x in split_top_level(str(val))]
    return [{"name": i} for i in items if i]

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

def normalize_cid(cid: str) -> str:
    """
    Canonical form for CMMC / NIST 800-171 control IDs.

    Examples:
      'SI.L2-3.14.1'  →  'SI.L2-3.14.1'
      'si.l2-3.14.1'  →  'SI.L2-3.14.1'
      'SI.L2 3.14.1'  →  'SI.L2-3.14.1'
    """
    cid = cid.strip().upper()
    cid = re.sub(r'\s*-\s*', '-', cid)
    cid = re.sub(r'\s+', '-', cid)
    return cid


def parse_control_id(token: str):
    """
    Parse a CMMC control ID token into (level, nist_ref).
    Input: "AC.L1-3.1.20" → ("L1", "3.1.20")
    Returns (None, None) on parse failure.
    """
    m = re.match(r'^[A-Z]+\.(L\d)-(.+)$', token.strip().upper())
    if m:
        return m.group(1), m.group(2)
    return None, None


def resolve_control(token: str) -> str | None:
    """
    Resolve a CMMC control ID to a Notion page ID using the NIST ref index.
    Prefers exact level match; falls back to any row with the same NIST ref.
    Returns page_id or None if unresolvable.
    """
    level, nist_ref = parse_control_id(token)
    if not nist_ref:
        return None
    candidates = CMMC_CACHE.get(nist_ref, [])
    if not candidates:
        return None
    for (row_level, page_id) in candidates:
        if row_level == level:
            return page_id
    print(f"    ⚠️  resolve_control: {token} — no {level} row; "
          f"falling back to {candidates[0][0]} row for ref {nist_ref}")
    return candidates[0][1]

# ===================================================================
# 6. PIPELINE FUNCTIONS
# ===================================================================

def get_show_notes(target_date: str = None) -> tuple:
    date_str = target_date or date.today().isoformat()
    print(f"📡 Fetching show notes for {date_str}...")
    listing_url = "https://cyberthreatbrief.simplycyber.io/episodes/"
    try:
        resp = requests.get(listing_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"❌ Could not reach episodes listing: {e}")
    soup = BeautifulSoup(resp.text, "html.parser")
    episode_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if date_str in href and "top-cyber-news-now" in href:
            episode_url = (
                href if href.startswith("http")
                else f"https://cyberthreatbrief.simplycyber.io{href}"
            )
            break
    if not episode_url:
        raise RuntimeError(
            f"❌ No episode found for {date_str}.\n"
            f"   Check: {listing_url}\n"
            f"   Episode may not be published yet — try again in 30 min."
        )
    print(f"📄 Episode found: {episode_url}")
    try:
        ep_resp = requests.get(episode_url, timeout=15)
        ep_resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"❌ Could not fetch episode page: {e}")
    ep_soup = BeautifulSoup(ep_resp.text, "html.parser")
    for tag in ep_soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()
    raw_text = ep_soup.get_text(separator="\n", strip=True)
    clean_text = scrub(raw_text)
    print(f"✅ Show notes ready: {len(clean_text.split()):,} words")
    return clean_text, episode_url


def _extract_episode_number(title: str) -> int | None:
    """Pulls the real episode number out of an RSS entry's title text
    (e.g. 'Top Cyber News NOW – Ep 1172 – ...'). Returns None if the title
    doesn't carry a recognizable 'Ep NNN' token — callers must treat that
    as 'no real episode number available', not guess one.
    Fallback only — see _resolve_episode_number(), which prefers the feed's
    own <itunes:episode>/<podcast:episode> tag over this title-text scrape."""
    m = re.search(r'Ep\.?\s*(\d{3,5})', title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _resolve_episode_number(entry, title: str) -> int | None:
    """Determines the real episode number for an RSS entry. Prefers the
    <itunes:episode> tag (feedparser exposes it as entry['itunes_episode'];
    <podcast:episode> carries the identical value on this feed and has no
    separate feedparser key) over _extract_episode_number()'s title-text
    regex — the title is hand-written by the show and can lag the real
    number. Confirmed live 2026-08-04: two consecutive days (08-03, 08-04)
    had a stale 'Ep NNN' in the title while <itunes:episode> had already
    incremented correctly, silently mis-numbering both days' records until
    caught by a manual audit. Falls back to the title regex only when the
    tag is absent or isn't a plain 3-5 digit number, so feeds/entries
    without itunes:episode still resolve exactly as before this fix.
    Logs a loud mismatch warning when title and tag disagree, so a future
    lag is visible in the run log instead of requiring another audit."""
    title_guess = _extract_episode_number(title)
    tag_val = entry.get("itunes_episode") if hasattr(entry, "get") else None
    if tag_val:
        tag_str = str(tag_val).strip()
        if re.fullmatch(r'\d{3,5}', tag_str):
            tag_num = int(tag_str)
            if title_guess and title_guess != tag_num:
                print(f"⚠️  Episode number mismatch: title text says 'Ep {title_guess}' "
                      f"but <itunes:episode> says {tag_num} — trusting the tag (title "
                      f"text is hand-written and known to lag).")
            return tag_num
        print(f"⚠️  <itunes:episode> present but not a plain 3-5 digit number "
              f"({tag_val!r}) — falling back to title text.")
    return title_guess


def get_rss_episode_date() -> tuple[str, str | None, str | None, int | None]:
    FEED_URL = "https://feeds.transistor.fm/simply-cyber"
    print(f"📡 Checking RSS feed for latest episode date: {FEED_URL}...")
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"❌ RSS feed parse failed: {feed.bozo_exception}")
    if not feed.entries:
        raise RuntimeError("❌ No episodes found in feed.")
    latest = feed.entries[0]
    title  = latest.get("title", "Unknown")
    parsed = latest.get("published_parsed")
    if not parsed:
        raise RuntimeError("❌ No pubDate found in latest feed entry.")
    date_str = f"{parsed.tm_year:04d}-{parsed.tm_mon:02d}-{parsed.tm_mday:02d}"
    ep_number = _resolve_episode_number(latest, title)
    youtube_url = None
    yt_id = latest.get("yt_videoid")
    if yt_id:
        youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
    else:
        for link in latest.get("links", []):
            href = link.get("href", "")
            if "youtube.com" in href or "youtu.be" in href:
                youtube_url = href
                break
    transistor_url = None
    encs = latest.get("enclosures")
    if encs:
        transistor_url = encs[0].get("href")
    print(f"✅ Latest episode: {title} → {date_str}"
          + (f" | Ep {ep_number}" if ep_number else " | ep# unrecognized")
          + (f" | YouTube: {youtube_url}" if youtube_url else ""))
    return date_str, youtube_url, transistor_url, ep_number


BARRICADE_LAST_FILE = SCRIPT_DIR / "barricade_last_ingested.txt"


def get_barricade_latest() -> tuple[str, str, str | None] | None:
    from youtube_transcript_api import YouTubeTranscriptApi
    FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UCLco-g6YIjhPqOBBR6CUXpg"
    print(f"📡 Checking Barricade Cyber RSS feed...")
    feed = feedparser.parse(FEED_URL)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"❌ Barricade RSS feed parse failed: {feed.bozo_exception}")
    if not feed.entries:
        raise RuntimeError("❌ No videos found in Barricade Cyber feed.")
    try:
        last_id = BARRICADE_LAST_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        last_id = ""
    ytt = YouTubeTranscriptApi()
    for entry in feed.entries[:15]:
        title    = entry.get("title", "Unknown")
        video_id = entry.get("yt_videoid") or entry.get("id", "").split(":")[-1]
        if not video_id:
            continue
        if video_id == last_id:
            print(f"⏭️  Already ingested: {title} ({video_id}) — nothing new.")
            return None
        try:
            ytt.fetch(video_id)
        except Exception as e:
            print(f"⛔  Skipping {title} ({video_id}): {e}")
            continue
        real_date = None
        parsed = entry.get("published_parsed")
        if parsed:
            real_date = f"{parsed.tm_year:04d}-{parsed.tm_mon:02d}-{parsed.tm_mday:02d}"
        print(f"✅ New video: {title} (ID: {video_id})"
              + (f" | published: {real_date}" if real_date else " | published date unavailable"))
        return video_id, title, real_date
    raise RuntimeError("❌ All 15 RSS entries are restricted or have no transcript available.")


def analyze_with_claude(content: str, url: str, today: str) -> str:
    print("🧠 Analyzing with Claude (claude-sonnet-4-6)...")
    user_message = (
        f"Source URL: {url}\n"
        f"Date Watched: {today}\n\n"
        f"CONTENT:\n{content}\n\n"
        f"[END OF TRANSCRIPT - BEGIN ANALYSIS]"
    )
    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=ANALYST_PROMPT,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )
    raw_output = message.content[0].text
    record_count = raw_output.count("===INTEL_RECORD_START===")
    print(f"✅ Claude analysis complete — {record_count} record(s) extracted")
    return raw_output

def analyze_with_claude_prompt(content: str, url: str, today: str, prompt: str) -> str:
    print("🧠 Analyzing with Claude (claude-sonnet-4-6)...")
    user_message = (
        f"Source URL: {url}\n"
        f"Date Watched: {today}\n\n"
        f"CONTENT:\n{content}\n\n"
        f"[END OF TRANSCRIPT - BEGIN ANALYSIS]"
    )
    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    raw_output = message.content[0].text
    record_count = raw_output.count("===INTEL_RECORD_START===")
    print(f"✅ Claude analysis complete — {record_count} record(s) extracted")
    return raw_output


def write_governance_file(content: str):
    starts = content.count("===INTEL_RECORD_START===")
    ends   = content.count("===INTEL_RECORD_END===")
    if starts != ends:
        print(f"⚠️  Marker mismatch — {starts} START vs {ends} END markers.")
        print(f"   Last record may be truncated. Consider increasing max_tokens.")
    out_path = SCRIPT_DIR / "governance_input.txt"
    out_path.write_text(content, encoding="utf-8")
    print(f"✅ Governance file written → {out_path.name}")


def load_mock_data() -> str:
    mock_path = SCRIPT_DIR / "governance_input.txt"
    if not mock_path.exists():
        raise FileNotFoundError(
            "❌ governance_input.txt not found.\n"
            "   Add records to the file first, then run --test again."
        )
    content = mock_path.read_text(encoding="utf-8")
    record_count = content.count("===INTEL_RECORD_START===")
    print(f"✅ Mock data loaded — {record_count} record(s) found")
    return content


def extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:live/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"❌ Could not extract video ID from: {url}")

def get_otx_pulses(api_key: str, lookback_hours: int = 24) -> list:
    from OTXv2 import OTXv2
    from datetime import datetime, timedelta
    RELEVANT_TAGS = {
        'ransomware', 'apt', 'nation-state',
        'critical-infrastructure', 'cisa',
        'supply-chain', 'phishing', 'identity',
        'malware', 'vulnerability', 'exploit',
        'lateral-movement', 'credential-access'
    }
    print(f"📡 Fetching OTX pulses (last {lookback_hours}hrs)...")
    since = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        otx    = OTXv2(api_key)
        pulses = otx.getall(modified_since=since)
    except Exception as e:
        raise RuntimeError(f"❌ OTX fetch failed: {e}")
    print(f"   Raw pulses last {lookback_hours}hrs: {len(pulses)}")
    def is_relevant(pulse):
        pulse_tags = {t.lower() for t in pulse.get('tags', [])}
        return bool(pulse_tags & RELEVANT_TAGS)
    relevant = [p for p in pulses if is_relevant(p)]
    print(f"   After relevance filter: {len(relevant)}")
    seen_ids = set()
    unique   = []
    for p in relevant:
        if p['id'] not in seen_ids:
            seen_ids.add(p['id'])
            unique.append(p)
    print(f"   After deduplication: {len(unique)} pulse(s) queued for Claude")
    results = []
    for p in unique:
        content = (
            f"Pulse: {p.get('name', 'Unknown')}\n"
            f"Description: {p.get('description', 'None')}\n"
            f"Tags: {', '.join(p.get('tags', []))}\n"
            f"Indicators: {len(p.get('indicators', []))} IOCs\n"
            f"Author: {p.get('author_name', 'Unknown')}\n"
            f"Created: {p.get('created', 'Unknown')}\n"
        )
        results.append({
            "content": content,
            "url":     f"https://otx.alienvault.com/pulse/{p['id']}",
            "name":    p.get('name', 'OTX Pulse'),
        })
    return results

def get_barricade_intel(url: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi, VideoUnplayable, TranscriptsDisabled
    video_id = extract_video_id(url)
    print(f"📡 Fetching transcript for video {video_id}...")
    ytt = YouTubeTranscriptApi()
    try:
        transcript = ytt.fetch(video_id)
    except VideoUnplayable:
        raise RuntimeError(f"❌ Video {video_id} is unplayable or restricted — no transcript available.")
    except TranscriptsDisabled:
        raise RuntimeError(f"❌ Video {video_id} has transcripts disabled — no transcript available.")
    raw_text = " ".join(snippet.text for snippet in transcript)
    clean_text = scrub(raw_text)
    print(f"✅ Transcript ready: {len(clean_text.split()):,} words")
    return clean_text


AUDIO_PREPASS_PROMPT = """You are extracting discrete cybersecurity news stories from a raw podcast
transcript. The transcript is conversational — ignore host banter, sponsor
reads, intros, and outros. For each distinct news story discussed, output:

Story N: [2-3 sentences. What happened, who was involved, the security
significance. Facts only — no analysis.]

Do not add clarifying glosses, translations, or your own labels for names
or terms mentioned in the transcript. Transcribe ambiguous terms exactly
as heard, with no interpretation of what they might refer to.

Output only the story list. No headers, no commentary, no formatting.
If a story is mentioned multiple times, output it once using the most
complete version."""


def get_audio_transcript(enclosure_url: str) -> str:
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError(
            "❌ Audio path requires CUDA — CPU fallback exceeds scheduler "
            "timeout. Aborting."
        )
    from faster_whisper import WhisperModel, decode_audio
    import tempfile

    SAMPLE_RATE = 16000
    CHUNK_SECONDS = 900  # 15 min — bounds peak STFT array to ~0.29 GiB
                         # regardless of total episode length (see
                         # architect_audio_ingest_memory_pressure_ticket.md);
                         # the old unchunked call built a 1.63 GiB array
                         # for a 91-min episode with zero cap.
    CHUNK_SAMPLES = CHUNK_SECONDS * SAMPLE_RATE

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = Path(tmpdir) / "episode.mp3"
        resp = requests.get(enclosure_url, stream=True, timeout=60)
        resp.raise_for_status()
        total_bytes = int(resp.headers.get("Content-Length", 0))
        print(f"📡 Downloading audio enclosure ({total_bytes / 1_048_576:.1f} MB): {enclosure_url}")
        with open(audio_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        print("🎙️ Transcribing with faster-whisper (large-v2, CUDA)...")
        model = WhisperModel("large-v2", device="cuda", compute_type="float16")

        # Decode once (mono float32 @16kHz); this array itself is cheap —
        # the STFT array built FROM it per model.transcribe() call was the
        # actual uncapped memory hazard, now bounded by chunking below.
        waveform = decode_audio(str(audio_path), sampling_rate=SAMPLE_RATE)
        total_samples = waveform.shape[0]
        num_chunks = -(-total_samples // CHUNK_SAMPLES)  # ceil div

        raw_text_parts = []
        for i in range(num_chunks):
            start = i * CHUNK_SAMPLES
            chunk_waveform = waveform[start:start + CHUNK_SAMPLES]
            print(f"  chunk {i + 1}/{num_chunks} ({chunk_waveform.shape[0] / SAMPLE_RATE:.0f}s)...")
            segments, _info = model.transcribe(chunk_waveform)
            raw_text_parts.append(" ".join(segment.text for segment in segments))

        raw_text = " ".join(raw_text_parts)

    clean_text = scrub(raw_text)
    print(f"✅ Transcript ready: {len(clean_text.split()):,} words")
    return clean_text


def extract_stories_from_transcript(transcript: str, url: str, today: str) -> str:
    print("🧠 Extracting stories from transcript (pre-pass)...")
    user_message = f"Source URL: {url}\nDate Watched: {today}\n\nTRANSCRIPT:\n{transcript}"
    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=AUDIO_PREPASS_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    story_summary = message.content[0].text
    print(f"✅ Story extraction complete — {len(story_summary.split()):,} words")
    return story_summary


def get_gemini_transcript(url: str) -> str:
    from google import genai
    from google.genai import types
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("❌ GEMINI_API_KEY not set in .env")
    client = genai.Client(api_key=gemini_key)
    print(f"📡 Sending to Gemini for transcription: {url}")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_uri(file_uri=url, mime_type="video/*"),
            (
                "Provide a complete, verbatim transcription of all spoken content in this video. "
                "Output only the spoken words as plain text, preserving natural paragraph breaks. "
                "Do not include timestamps, speaker labels, or any commentary."
            ),
        ]
    )
    raw_text = response.text
    clean_text = scrub(raw_text)
    print(f"✅ Gemini transcript ready: {len(clean_text.split()):,} words")
    return clean_text


def ingest_manual_transcript(raw_transcript: str, source_url: str) -> None:
    """Manual-paste ingest path. Supersedes Choice 2's old direct
    parse_records()+push_all() flow. Mirrors the audio-ingest path's full
    call chain — Call 1 then Call 2 — because extract_stories_from_transcript()
    only produces plain-text story prose, not INTEL_RECORD-tagged output."""
    story_summary = extract_stories_from_transcript(
        raw_transcript, source_url, date.today().isoformat()
    )
    raw_output = analyze_with_claude(
        story_summary, source_url, date.today().isoformat()
    )
    write_governance_file(raw_output)
    records = parse_records(SCRIPT_DIR / "governance_input.txt")
    write_pending_review(records, source_url)
    print(f"⏸  {len(records)} manual-paste record(s) awaiting manual review — "
          f"not pushed. Review {PENDING_REVIEW_FILE.name}, then run with "
          f"--push-reviewed to push after confirming.")


# ===================================================================
# 7. NOTION FUNCTIONS
# ===================================================================

def load_cmmc_cache(retries: int = 3, delay: int = 15):
    """
    Loads CMMC Control IDs into memory indexed by NIST 800-171 Ref.
    Retries up to 3 times on rate limit before giving up.
    """
    if not CMMC_DB_ID:
        print("⚠️  CMMC_DB_ID not configured — skipping cache")
        return

    for attempt in range(1, retries + 1):
        print(f"📡 Loading CMMC cache (attempt {attempt}/{retries})...")
        try:
            has_more = True
            cursor   = None
            while has_more:
                kwargs = {"database_id": CMMC_DB_ID, "page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                res = notion.databases.query(**kwargs)
                for page in res.get("results", []):
                    props     = page["properties"]
                    nist_prop = props.get("NIST 800-171 Ref", {}).get("rich_text", [])
                    nist_ref  = nist_prop[0].get("plain_text", "").strip() if nist_prop else ""
                    mat_prop  = props.get("Maturity", {}).get("select") or {}
                    maturity  = mat_prop.get("name", "").strip()
                    if nist_ref:
                        CMMC_CACHE[nist_ref].append((maturity, page["id"]))
                has_more = res.get("has_more", False)
                cursor   = res.get("next_cursor")
            print(f"✅ CMMC cache loaded: {len(CMMC_CACHE)} controls")
            return
        except Exception as e:
            err_str = str(e).lower()
            if "unauthorized" in err_str or "401" in err_str or "invalid_token" in err_str:
                print(f"❌ CMMC cache: credential error — {e}")
                return
            if attempt < retries:
                print(f"⏳ CMMC cache error (attempt {attempt}/{retries}) — retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                print(f"❌ CMMC cache failed after {retries} attempts: {e}")


def update_compliance_status(control_ids: List[str], log_page_url: str):
    """Writes back to CMMC database to mark evidence."""
    for cid in control_ids:
        page_id = resolve_control(cid)
        if page_id:
            try:
                notion.pages.update(
                    page_id=page_id,
                    properties={
                        "Status":        {"select": {"name": "Evidence Pending"}},
                        "Last Evidence": {"url": log_page_url}
                    }
                )
                print(f"📡 GRC UPDATE: {cid} → Evidence Pending")
            except Exception as e:
                print(f"⚠️  GRC update failed for {cid}: {e}")

# ===================================================================
# 8. THE ENGINE (PUSH_RECORD)
# ===================================================================

class DedupCheckError(RuntimeError):
    """Raised when a Notion dedup/prefix-count query cannot be completed after
    retries. Callers must fail CLOSED (treat as unresolved, not as 'new') —
    never assume 'doesn't exist' on a query we couldn't actually run."""
    pass


def _notion_query_all(filter_dict: dict, max_retries: int = 3, delay: float = 1.5) -> list:
    """Runs a Notion database query to exhaustion (all pages), retrying
    transient failures. Raises DedupCheckError after max_retries — the
    caller decides how to fail closed, this never silently returns []
    on a real failure."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            results = []
            cursor = None
            while True:
                kwargs = {"database_id": DATABASE_ID, "filter": filter_dict, "page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                res = notion.databases.query(**kwargs)
                results.extend(res.get("results", []))
                if not res.get("has_more"):
                    break
                cursor = res.get("next_cursor")
            return results
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"⚠️  Notion query failed (attempt {attempt}/{max_retries}): {e} — retrying in {delay}s")
                time.sleep(delay)
    raise DedupCheckError(f"Notion query failed after {max_retries} attempts: {last_exc}")


def record_exists(record_id: str) -> bool:
    """Query CPE Tracker for an exact record_id match. Returns False for
    malformed IDs. Fails CLOSED on real query failures — raises
    DedupCheckError after retries exhausted rather than silently assuming
    'doesn't exist' (the old behavior let a transient API error push a
    duplicate through unnoticed)."""
    if not record_id or str(record_id).lower() in ("unknown", "none", "empty", "n/a"):
        return False
    results = _notion_query_all({"property": "record_id", "rich_text": {"equals": record_id}})
    return len(results) > 0


def count_existing_record_ids_with_prefix(prefix: str) -> int:
    """Counts live records whose record_id starts with prefix. Used to seed
    the sequential index of a deterministically-constructed record_id so a
    second same-day run continues numbering instead of colliding with an
    earlier run's records."""
    results = _notion_query_all({"property": "record_id", "rich_text": {"starts_with": prefix}})
    return len(results)


def find_record_page(record_id: str) -> dict | None:
    """Looks up the live Notion page for a record_id, reusing the exact same
    query shape record_exists()/load_cmmc_cache() already use — no new query
    type, no new API surface. Returns the full page object (so callers get
    both the page id and its current property values from one query, not a
    separate fetch) or None if no matching page exists. Fails CLOSED like
    record_exists() — raises DedupCheckError after retries exhausted rather
    than assuming 'not found' on a real query failure.
    See boards/sentinel_update_existing_record_design.md, section 3."""
    if not record_id or str(record_id).lower() in ("unknown", "none", "empty", "n/a"):
        return None
    results = _notion_query_all({"property": "record_id", "rich_text": {"equals": record_id}})
    return results[0] if results else None


def _live_field_value_display(page: dict, field: str) -> str:
    """Renders a Notion page property's current live value as a plain string
    for the before/after correction diff — the read-side mirror of
    to_text()/to_multi()/to_select()."""
    prop = page.get("properties", {}).get(field)
    if prop is None:
        return "(property not found on page)"
    if field in RICH_TEXT_FIELDS:
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if field in MULTI_SELECT_FIELDS:
        return ", ".join(o.get("name", "") for o in prop.get("multi_select", []))
    if field in SELECT_FIELDS:
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    return "(unsupported field type for display)"


def _build_correction_payload(field: str, new_value: str) -> dict | None:
    """Builds the single-property notion.pages.update payload for a
    correction, reusing the exact same to_text()/to_multi()/to_select()
    serializers push_record() already uses for the same fields — no new
    serialization logic. Returns None for a field type this mechanism
    doesn't know how to write (caller must treat that as unsupported, not
    silently skip the property)."""
    if field in RICH_TEXT_FIELDS:
        return {field: {"rich_text": to_text(new_value)}}
    if field in MULTI_SELECT_FIELDS:
        return {field: {"multi_select": to_multi(new_value)}}
    if field in SELECT_FIELDS:
        return {field: {"select": to_select(new_value)}}
    return None


SOURCE_SLUG_MAP = {
    "Simply Cyber Daily Threat Brief": "simplycyber",
    "Barricade Cyber": "barricadecyber",
    "AlienVault OTX": "alienvault-otx",
}


def _slugify(text: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', text.strip().lower()).strip('-')
    return s or "unknown-source"


def source_slug(source_label: str) -> str:
    return SOURCE_SLUG_MAP.get(source_label, _slugify(source_label))


def _construct_record_id(source_label: str, real_date: str | None, ep_number,
                          seq_cache: Dict[str, int]) -> str:
    """Deterministically builds record_id — the model's own record_id:: output
    is discarded entirely, this is now the only source of truth for identity.
    Sequential index is seeded from a live Notion count (via
    count_existing_record_ids_with_prefix), not a local/in-memory counter, so
    a second run against the same calendar date continues numbering instead
    of restarting at -01 and colliding with the first run's records."""
    slug = source_slug(source_label)
    if real_date and ep_number:
        prefix = f"{slug}-ep{int(ep_number):04d}-{real_date}"
    elif real_date:
        prefix = f"{slug}-{real_date}"
    else:
        prefix = f"{slug}-manual-{date.today().isoformat()}"

    if prefix not in seq_cache:
        seq_cache[prefix] = count_existing_record_ids_with_prefix(prefix) + 1
    seq = seq_cache[prefix]
    seq_cache[prefix] = seq + 1
    return f"{prefix}-{seq:02d}"


def push_record(record: dict, source_label: str, url: str, seq_cache: Dict[str, int],
                 real_date: str | None = None, ep_number=None) -> tuple[bool, str | None]:
    try:
        record_id = _construct_record_id(source_label, real_date, ep_number, seq_cache)
    except DedupCheckError as e:
        print(f"❌ DEDUP-CHECK-FAILED constructing record_id ({source_label}): {e}")
        return False, "dedup-check-failed"

    record["record_id"] = record_id
    page_title = f"{source_label} - {record_id}"

    try:
        if record_exists(record_id):
            print(f"⏭️  {record_id} already exists — skipping")
            return True, None
    except DedupCheckError as e:
        print(f"❌ DEDUP-CHECK-FAILED for {record_id}: {e}")
        return False, "dedup-check-failed"

    props = {
        "Title":        {"title": [{"text": {"content": page_title}}]},
        "url":          {"url": url} if url else {},
        "date_watched": {"date": {"start": date.today().isoformat()}},
        "cpe_credits":  {"number": 0.5},
    }

    for key, val in record.items():
        if key in SKIP_FIELDS or not val:
            continue
        if str(val).lower() in ("none", "unknown", "empty", "n/a"):
            continue
        if key in SELECT_FIELDS:
            props[key] = {"select": to_select(val)}
        elif key in MULTI_SELECT_FIELDS:
            props[key] = {"multi_select": to_multi(val)}
        elif key in RICH_TEXT_FIELDS:
            props[key] = {"rich_text": to_text(val)}
        elif key in DATE_FIELDS:
            val_str = str(val).strip()
            if val_str and not val_str.startswith('T'):
                props[key] = {"date": {"start": val_str}}
        elif key in NUMBER_FIELDS:
            try:
                props[key] = {"number": float(val)}
            except (ValueError, TypeError):
                pass

    # === CMMC / Master Frameworks Relation ===
    cmmc_raw = (
        record.get("Master Frameworks(CMMC 2.0 / NIST 800-171)", "") or
        record.get("cmmc_mapping", "")
    )
    if cmmc_raw and str(cmmc_raw).lower() not in ("none", "unknown"):
        cids_raw = [x.strip() for x in cmmc_raw.split(",") if x.strip()]
        rels   = []
        missed = []
        for cid in cids_raw:
            pid = resolve_control(cid)
            if pid:
                rels.append({"id": pid})
            else:
                missed.append(cid)
        if rels:
            props["Master Frameworks(CMMC 2.0 / NIST 800-171)"] = {"relation": rels}
            print(f"    🔗 Linked {len(rels)} CMMC control(s)")
        if missed:
            print(f"    ⚠️  Unresolved CMMC IDs: {missed}")
            CMMC_MISSES.extend(f"{record_id}: {m}" for m in missed)

    # === Learning Plan Relation (Auto-detect from content) ===
    linked_weeks = set()

    learning_raw = (
        record.get("GRC_Learning_Plan_All_Phases", "") or
        record.get("learning_phase", "")
    )
    if learning_raw:
        phase_key = re.split(r'\s[–-]\s', learning_raw)[0].strip()
        if phase_key in LEARNING_CACHE:
            linked_weeks.add(phase_key)

    # removed 2026-07-21 — undocumented bulk fanout. DOMAIN_TO_WEEKS/
    # CATEGORY_TO_WEEKS unioned every control_domains/intel_category tag hit
    # into this relation with no cap or relevance check, against
    # canonical_schema_v1.md's "one deliberately-chosen link per week"
    # doctrine. Found via live-data audit: 14/64 weeks non-empty, 13-123
    # links each, near-zero topical relevance on manual sampling. Dicts left
    # in place (lines 167-194) in case there's another use for them — only
    # this usage is removed.
    # domains_raw = record.get("control_domains", "") or ""
    # for domain in [d.strip() for d in domains_raw.split(",")]:
    #     for week in DOMAIN_TO_WEEKS.get(domain, []):
    #         linked_weeks.add(week)
    #
    # cats_raw = record.get("intel_category", "") or ""
    # for cat in [c.strip() for c in cats_raw.split(",")]:
    #     for week in CATEGORY_TO_WEEKS.get(cat, []):
    #         linked_weeks.add(week)

    if linked_weeks:
        relation_ids = [
            {"id": LEARNING_CACHE[w]}
            for w in sorted(linked_weeks)
            if w in LEARNING_CACHE and LEARNING_CACHE[w]
        ]
        if relation_ids:
            props["GRC_Learning_Plan_All_Phases"] = {"relation": relation_ids}
            print(f"    🔗 Linked Learning Plan: {', '.join(sorted(linked_weeks))}")

    try:
        response = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=props
        )
        log_url = response.get("url")
        if cmmc_raw and log_url:
            update_compliance_status(
                [x.strip() for x in cmmc_raw.split(",") if x.strip()],
                log_url
            )
        print(f"✅ Logged: {record_id}")
        return True, None
    except Exception as e:
        print(f"❌ Failed: {record_id} | {e}")
        return False, "push-failed"

# ===================================================================
# 9. PARSER
# ===================================================================

def parse_records(file_path: Path) -> List[dict]:
    """Extracts all intel records from a governance_input.txt file."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    blocks  = re.findall(
        r'===INTEL_RECORD_START===(.*?)===INTEL_RECORD_END===',
        content,
        re.DOTALL
    )
    records = []
    for block in blocks:
        raw = {}
        current_key = None
        for line in block.strip().split('\n'):
            if '::' in line:
                k, v = line.split('::', 1)
                current_key = k.strip()
                raw[current_key] = v.strip()
            elif current_key and line.strip():
                raw[current_key] += ' ' + line.strip()
        if raw.get('record_id'):
            records.append(raw)
    return records


CORRECTIONS_FILE = SCRIPT_DIR / "record_corrections.txt"


def parse_corrections(file_path: Path) -> List[dict]:
    """Extracts field-level corrections from a corrections file. Same
    block-delimiter parsing approach as parse_records() (one regex findall
    over START/END markers, then `key:: value` lines with multi-line
    continuation) — different marker pair and required-key set, not a new
    parsing paradigm. A block missing record_id/field/new_value is dropped
    with a warning rather than silently producing a partial correction."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    blocks = re.findall(
        r'===RECORD_CORRECTION_START===(.*?)===RECORD_CORRECTION_END===',
        content,
        re.DOTALL
    )
    corrections = []
    for block in blocks:
        raw = {}
        current_key = None
        for line in block.strip().split('\n'):
            if '::' in line:
                k, v = line.split('::', 1)
                current_key = k.strip()
                raw[current_key] = v.strip()
            elif current_key and line.strip():
                raw[current_key] += ' ' + line.strip()
        if raw.get('record_id') and raw.get('field') and raw.get('new_value'):
            corrections.append(raw)
        else:
            print(f"⚠️  Skipping malformed correction block (missing record_id/field/new_value): {raw}")
    return corrections


def push_all(records: list, source_label: str, url: str) -> int:
    """Pushes all records and saves any failures for retry.
    Returns the count of failures specifically caused by a dedup-check
    exhausting its retries (as opposed to a real push failure) — 0 when
    none occurred — so unattended (--auto*) callers can decide whether to
    exit with a distinct non-zero code instead of the generic failure code."""
    if not records:
        print("❌ No records parsed — check delimiters / input file. Nothing pushed.")
        return 0
    failed = []
    dedup_failure_count = 0
    seq_cache: Dict[str, int] = {}
    for r in records:
        rec_real_date = r.pop("_real_date", None)
        rec_ep_number = r.pop("_real_ep_number", None)
        success, reason = push_record(r, source_label, url, seq_cache, rec_real_date, rec_ep_number)
        if not success:
            if reason == "dedup-check-failed":
                dedup_failure_count += 1
            if reason:
                r["_fail_reason"] = reason
            failed.append(r)
        time.sleep(0.4)

    if failed:
        fail_path = SCRIPT_DIR / "failed_records.txt"
        with open(fail_path, "a", encoding="utf-8") as f:
            for r in failed:
                f.write("===INTEL_RECORD_START===\n")
                for k, v in r.items():
                    f.write(f"{k}:: {v}\n")
                f.write("===INTEL_RECORD_END===\n\n")
        print(f"⚠️  {len(failed)} record(s) failed — saved to failed_records.txt"
              + (f" ({dedup_failure_count} dedup-check-failed)" if dedup_failure_count else ""))
    else:
        print(f"✅ All {len(records)} record(s) pushed successfully.")
    return dedup_failure_count

PENDING_REVIEW_FILE = SCRIPT_DIR / "audio_review_pending.txt"


def write_pending_review(records: list, url: str) -> None:
    """Appends audio-ingest records to the pending-review file for manual AO confirmation.
    Append, not overwrite — a second thin-notes day landing before the first
    pending batch is reviewed must not clobber it; both must survive until
    --push-reviewed processes them."""
    if not records:
        print("⚠️  No records to hold for review — nothing written.")
        return
    with open(PENDING_REVIEW_FILE, "a", encoding="utf-8") as f:
        for r in records:
            row = dict(r)
            if str(row.get("url", "")).strip().lower() in ("", "none", "unknown"):
                row["url"] = url
            f.write("===INTEL_RECORD_START===\n")
            for k, v in row.items():
                f.write(f"{k}:: {v}\n")
            f.write("===INTEL_RECORD_END===\n\n")
    print(f"✅ {len(records)} record(s) appended to {PENDING_REVIEW_FILE.name} for manual review.")


def confirm_and_push_reviewed() -> None:
    """Pushes AO-reviewed audio-ingest records, grouped by each record's own
    url (so a stacked second thin-notes day keeps its own episode url), then
    archives the pending file so a repeat run does not double-push."""
    if not PENDING_REVIEW_FILE.exists():
        print(f"✅ No pending review file found ({PENDING_REVIEW_FILE.name}) — nothing to push.")
        return
    records = parse_records(PENDING_REVIEW_FILE)
    if not records:
        print("⚠️  Pending review file exists but contains no valid records — check formatting.")
        return
    groups: Dict[str, list] = defaultdict(list)
    for r in records:
        groups[r.get("url", "unknown")].append(r)
    for grp_url, group in groups.items():
        print(f"\n📋 Pushing {len(group)} reviewed record(s) for {grp_url}...")
        push_all(group, "Simply Cyber Daily Threat Brief", grp_url)
    archive_path = PENDING_REVIEW_FILE.with_name(
        f"{PENDING_REVIEW_FILE.stem}_pushed_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    )
    PENDING_REVIEW_FILE.replace(archive_path)
    print(f"✅ Pending review file archived → {archive_path.name}")


# Low-friction path per boards/sentinel_update_existing_record_design.md
# section 4 — free-text/prose fields most likely to carry a factual
# fabrication. Anything outside this set still goes through, just with an
# explicit warning banner first (process guard, not a code-level block).
IN_SCOPE_CORRECTION_FIELDS = {
    "key_takeaways", "executive_summary", "operational_relevance",
    "identity_impact", "detection_opportunities",
}

# Fields named in the approved design that turn out NOT to be persisted as
# their own live Notion property, discovered during this build (not assumed
# from the design doc alone) — there is nothing live to correct for these,
# so they're refused with an explanation rather than silently producing an
# empty/misleading diff.
CORRECTION_FIELD_UNAVAILABLE = {
    "title": (
        "'title' is never persisted as its own Notion property — push_record() "
        "discards the LLM's title:: output entirely (it's in SKIP_FIELDS). The "
        "live page's Title is auto-generated from source_label + record_id, not "
        "analyst content, so there is no live field here to correct."
    ),
}


def _confirm(prompt: str) -> bool:
    """Interactive y/n gate. Matches this codebase's existing input()
    convention. Blank or anything other than a leading 'y'/'yes' is treated
    as a no — never a default-yes, since this gates a live production write."""
    ans = input(prompt).strip().lower()
    return ans in ("y", "yes")


def push_corrections() -> None:
    """Applies AO-reviewed field-level corrections to already-live Notion
    records. Permanently manual/interactive — never wired into any --auto*
    path, and no batch-apply-without-looking flag exists on purpose. Every
    correction gets its own before/after diff (current live value vs.
    new_value) and its own explicit y/n confirmation, then an immediate
    post-write re-query so the re-verification is part of this command's own
    output rather than something a human has to remember to do separately.
    See boards/sentinel_update_existing_record_design.md, sections 2 and 5."""
    if not CORRECTIONS_FILE.exists():
        print(f"✅ No corrections file found ({CORRECTIONS_FILE.name}) — nothing to push.")
        return
    corrections = parse_corrections(CORRECTIONS_FILE)
    if not corrections:
        print("⚠️  Corrections file exists but contains no valid blocks — check formatting.")
        return

    applied = declined = skipped = 0
    for i, corr in enumerate(corrections, start=1):
        record_id = corr["record_id"]
        field     = corr["field"]
        new_value = corr["new_value"]
        reason    = corr.get("reason", "(no reason given)")

        print(f"\n--- Correction {i}/{len(corrections)}: {record_id} · {field} ---")

        if field in CORRECTION_FIELD_UNAVAILABLE:
            print(f"❌ Cannot correct '{field}': {CORRECTION_FIELD_UNAVAILABLE[field]}")
            skipped += 1
            continue

        if field not in IN_SCOPE_CORRECTION_FIELDS:
            print(
                "⚠️  FIELD OUTSIDE NORMAL SCOPE — this field has a history of "
                "independent hand-editing; confirm this correction won't revert "
                "an unrelated fix."
            )

        try:
            page = find_record_page(record_id)
        except DedupCheckError as e:
            print(f"❌ Lookup failed for {record_id}: {e}")
            skipped += 1
            continue

        if page is None:
            print(f"❌ No live record found for record_id '{record_id}' — skipping.")
            skipped += 1
            continue

        payload = _build_correction_payload(field, new_value)
        if payload is None:
            print(f"❌ '{field}' is not a recognized/supported property type for correction — skipping.")
            skipped += 1
            continue

        current_value = _live_field_value_display(page, field)
        print(f"  current:  {current_value}")
        print(f"  new:      {new_value}")
        print(f"  reason:   {reason}")

        if not _confirm("  Apply this correction? [y/N]: "):
            print("  ⏭️  Declined — not applied.")
            declined += 1
            continue

        try:
            notion.pages.update(page_id=page["id"], properties=payload)
        except Exception as e:
            print(f"  ❌ Write failed: {e}")
            skipped += 1
            continue

        try:
            verify_page = find_record_page(record_id)
            verify_value = _live_field_value_display(verify_page, field) if verify_page else "(re-query found no page)"
        except DedupCheckError as e:
            print(f"  ⚠️  Write succeeded but re-verification query failed: {e} — check manually.")
            applied += 1
            continue

        print(f"  ✅ Applied. Re-verified live value: {verify_value}")
        applied += 1

    print(
        f"\n📋 Corrections summary: {applied} applied, {declined} declined, "
        f"{skipped} skipped (out of {len(corrections)} total)."
    )

# ===================================================================
# 10. MAIN
# ===================================================================

def main():
    print("\n" + "="*60)
    print("⚔️   DARKSWORD — GRC Intelligence Platform V7.0")
    if TEST_MODE:
        print("     💡 TEST MODE  |  $0.00  |  API Disconnected")
    elif AUTO_MODE:
        print("     🤖 AUTO MODE  |  RSS → Show Notes → Claude → Notion")
    elif AUTO_OTX_MODE:
        print("     🤖 AUTO-OTX        |  AlienVault OTX → Claude → Notion")
    elif AUTO_BARRICADE_MODE:
        print("     🤖 AUTO-BARRICADE  |  Barricade Cyber → Claude → Notion")
    elif PUSH_REVIEWED_MODE:
        print("     🔎 PUSH-REVIEWED  |  audio_review_pending.txt → Notion")
    elif PUSH_CORRECTIONS_MODE:
        print("     ✏️  PUSH-CORRECTIONS  |  record_corrections.txt → Notion (interactive diff+confirm)")
    else:
        print("     🔴 LIVE MODE  |  API Connected")
    print("="*60)

    load_cmmc_cache()

    if PUSH_REVIEWED_MODE:
        confirm_and_push_reviewed()
        return

    if PUSH_CORRECTIONS_MODE:
        push_corrections()
        return

    if AUTO_MODE:
        print("\n⚡ Auto-run: Choice 5 (RSS date detection → Show Notes → Notion)")
        try:
            date_str, youtube_url, transistor_url, ep_number = get_rss_episode_date()
        except (RuntimeError, ValueError) as e:
            print(f"❌ Auto pipeline failed: {e}")
            sys.exit(1)
        today_str = date.today().isoformat()
        if date_str < today_str:
            print(f"⚠️  RSS latest episode is {date_str} — today is {today_str}. No new episode published. Exiting cleanly.")
            sys.exit(0)
        try:
            content, url          = get_show_notes(date_str)
        except (RuntimeError, ValueError) as e:
            print(f"❌ Auto pipeline failed: {e}")
            sys.exit(1)

        word_count = len(content.split())
        source_is_audio_ingest = False
        if word_count < 500:
            print(f"⚠️  Show notes too short ({word_count} words) — attempting audio ingest.")
            if not transistor_url:
                print("❌ No Transistor enclosure URL in RSS feed — cannot fall back. Exiting.")
                sys.exit(1)
            try:
                raw_transcript = get_audio_transcript(transistor_url)
                content = extract_stories_from_transcript(raw_transcript, transistor_url, date.today().isoformat())
                url = transistor_url
                source_is_audio_ingest = True
            except (RuntimeError, ValueError) as e:
                print(f"❌ Audio ingest failed: {e} — exiting. Manual ingest required.")
                sys.exit(1)

        try:
            raw_output = analyze_with_claude(content, url, date.today().isoformat())
            write_governance_file(raw_output)
        except (RuntimeError, ValueError) as e:
            print(f"❌ Auto pipeline failed: {e}")
            sys.exit(1)
        records = parse_records(SCRIPT_DIR / "governance_input.txt")
        for r in records:
            r["_real_date"] = date_str
            if ep_number:
                r["_real_ep_number"] = str(ep_number)

        if source_is_audio_ingest:
            write_pending_review(records, url)
            print(f"⏸  {len(records)} audio-ingest record(s) awaiting manual review — "
                  f"not pushed. Review {PENDING_REVIEW_FILE.name}, then run with "
                  f"--push-reviewed to push after confirming.")
        else:
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            dedup_failures = push_all(records, "Simply Cyber Daily Threat Brief", url)
            if not records and word_count >= 500:
                print(
                    f"\n⚠️  WARNING: 0 records pushed despite {word_count}-word show notes. "
                    "Claude ran but the parser found no valid INTEL_RECORD blocks. "
                    "Check governance_input.txt and review Claude output for formatting issues."
                )
            if dedup_failures:
                print(f"❌ DEDUP-CHECK-FAILED: {dedup_failures} record(s) could not be "
                      f"verified against Notion this run — held in failed_records.txt, "
                      f"NOT assumed new, NOT assumed duplicate.")
                sys.exit(3)
        return

    if AUTO_OTX_MODE:
        print("\n⚡ Auto-OTX: Choice 4 (AlienVault OTX → Claude → Notion)")
        otx_key = os.getenv("OTX_API_KEY")
        if not otx_key:
            print("❌ OTX_API_KEY not set in .env")
            sys.exit(1)
        try:
            pulses = get_otx_pulses(otx_key, LOOKBACK_HOURS)
        except RuntimeError as e:
            print(f"❌ OTX fetch failed: {e}")
            sys.exit(1)
        if not pulses:
            print(f"✅ No relevant pulses found in last {LOOKBACK_HOURS}hrs — nothing to push.")
            return
        print(f"\n📋 Sending {len(pulses)} pulse(s) to Claude...")
        all_records = []
        for pulse in pulses:
            raw = analyze_with_claude_prompt(
                pulse["content"],
                pulse["url"],
                date.today().isoformat(),
                OTX_ANALYST_PROMPT
            )
            write_governance_file(raw)
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            all_records.extend(records)
        print(f"\n📋 Pushing {len(all_records)} record(s) to Notion...")
        dedup_failures = push_all(all_records, "AlienVault OTX", "https://otx.alienvault.com")
        if dedup_failures:
            print(f"❌ DEDUP-CHECK-FAILED: {dedup_failures} record(s) could not be "
                  f"verified against Notion this run — held in failed_records.txt, "
                  f"NOT assumed new, NOT assumed duplicate.")
            sys.exit(3)
        return

    if AUTO_BARRICADE_MODE:
        print("\n⚡ Auto-Barricade: (YouTube RSS → Transcript → Claude → Notion)")
        try:
            result = get_barricade_latest()
        except RuntimeError as e:
            print(f"❌ Barricade RSS fetch failed: {e}")
            sys.exit(1)
        if result is None:
            return
        video_id, _title, barricade_date = result
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            content = get_barricade_intel(url)
            raw_output = analyze_with_claude(content, url, date.today().isoformat())
            write_governance_file(raw_output)
        except (RuntimeError, ValueError) as e:
            print(f"❌ Barricade pipeline failed: {e}")
            sys.exit(1)
        records = parse_records(SCRIPT_DIR / "governance_input.txt")
        if barricade_date:
            for r in records:
                r["_real_date"] = barricade_date
        print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
        dedup_failures = push_all(records, "Barricade Cyber", url)
        BARRICADE_LAST_FILE.write_text(video_id, encoding="utf-8")
        if dedup_failures:
            print(f"❌ DEDUP-CHECK-FAILED: {dedup_failures} record(s) could not be "
                  f"verified against Notion this run — held in failed_records.txt, "
                  f"NOT assumed new, NOT assumed duplicate.")
            sys.exit(3)
        return

    while True:
        print("\n1. Autonomous Pipeline  (Show Notes → Claude → Notion)")
        print("2. Manual Transcript Ingest (clipboard → Claude → review-gate)")
        if TEST_MODE:
            print("3. Test Pipeline        (Mock data → Notion) ← YOU ARE HERE")
        print("4. OTX Pipeline         (AlienVault → Claude → Notion)")
        print("5. RSS Feed Pipeline    (Barricade Cyber → Claude → Notion)")
        print("6. Barricade Cyber      (YouTube Transcript → Claude → Notion)")
        print("7. Simply Cyber YouTube (YouTube Transcript → Claude → Notion)  ← show notes fallback")
        print("8. Gemini YouTube Ingest (restricted/long-form → Claude → Notion)")
        print("0. Exit")

        choice = input("\nSelection: ").strip()

        if choice == "0":
            break

        elif choice == "1":
            if TEST_MODE:
                print("❌ Autonomous mode disabled in --test. Run without --test flag.")
                continue
            date_input = input("Date (YYYY-MM-DD, blank = today): ").strip() or None
            try:
                content, url = get_show_notes(date_input)
                raw_output = analyze_with_claude(content, url, date.today().isoformat())
                write_governance_file(raw_output)
            except (RuntimeError, ValueError, FileNotFoundError) as e:
                print(f"❌ Pipeline failed: {e}")
                continue
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, "Simply Cyber Daily Threat Brief", url)

        elif choice == "2":
            if TEST_MODE:
                print("❌ Manual transcript ingest disabled in --test.")
                continue
            while True:
                url = input("Source URL: ").strip()
                if url:
                    break
                print("⚠️  URL cannot be empty — records will have no source attribution. Enter a URL.")
            print("\n📄 Reading transcript from clipboard...")
            raw_transcript = pyperclip.paste()
            if not raw_transcript or len(raw_transcript) < 50:
                print("❌ Clipboard is empty or contains junk data — nothing to ingest.")
                continue
            ingest_manual_transcript(raw_transcript, url)

        elif choice == "3" and TEST_MODE:
            while True:
                url = input("Source URL (for metadata): ").strip()
                if url:
                    break
                print("⚠️  URL cannot be empty — records will have no source attribution. Enter a URL.")
            try:
                raw_output = load_mock_data()
            except FileNotFoundError as e:
                print(e)
                continue
            write_governance_file(raw_output)
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, "Simply Cyber Daily Threat Brief", url)
        elif choice == "4":
            if TEST_MODE:
                print("❌ OTX mode disabled in --test.")
                continue
            otx_key = os.getenv("OTX_API_KEY")
            if not otx_key:
                print("❌ OTX_API_KEY not set in .env")
                continue
            try:
                pulses = get_otx_pulses(otx_key, LOOKBACK_HOURS)
            except RuntimeError as e:
                print(e)
                continue
            if not pulses:
                print(f"✅ No relevant pulses found in last {LOOKBACK_HOURS}hrs.")
                continue
            print(f"\n📋 Sending {len(pulses)} pulse(s) to Claude...")
            all_records = []
            for pulse in pulses:
                raw = analyze_with_claude_prompt(
                    pulse["content"],
                    pulse["url"],
                    date.today().isoformat(),
                    OTX_ANALYST_PROMPT
                )
                write_governance_file(raw)
                records = parse_records(SCRIPT_DIR / "governance_input.txt")
                all_records.extend(records)
            print(f"\n📋 Pushing {len(all_records)} record(s) to Notion...")
            push_all(all_records, "AlienVault OTX", "https://otx.alienvault.com")

        elif choice == "5":
            if TEST_MODE:
                print("❌ RSS auto-detect mode disabled in --test.")
                continue
            try:
                date_str, _yt, _transistor, ep_number = get_rss_episode_date()
                content, url    = get_show_notes(date_str)
                raw_output      = analyze_with_claude(content, url, date.today().isoformat())
                write_governance_file(raw_output)
            except (RuntimeError, ValueError) as e:
                print(f"❌ Pipeline failed: {e}")
                continue
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            for r in records:
                r["_real_date"] = date_str
                if ep_number:
                    r["_real_ep_number"] = str(ep_number)
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, "Simply Cyber Daily Threat Brief", url)

        elif choice == "6":
            if TEST_MODE:
                print("❌ Barricade Cyber mode disabled in --test.")
                continue
            url = input("Barricade Cyber YouTube URL: ").strip()
            try:
                content = get_barricade_intel(url)
                raw_output = analyze_with_claude(content, url, date.today().isoformat())
                write_governance_file(raw_output)
            except (RuntimeError, ValueError) as e:
                print(f"❌ Pipeline failed: {e}")
                continue
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, "Barricade Cyber", url)

        elif choice == "7":
            if TEST_MODE:
                print("❌ Simply Cyber YouTube fallback disabled in --test.")
                continue
            url = input("Simply Cyber YouTube URL: ").strip()
            try:
                content = get_barricade_intel(url)
                raw_output = analyze_with_claude(content, url, date.today().isoformat())
                write_governance_file(raw_output)
            except (RuntimeError, ValueError) as e:
                print(f"❌ Pipeline failed: {e}")
                continue
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, "Simply Cyber Daily Threat Brief", url)

        elif choice == "8":
            if TEST_MODE:
                print("❌ Gemini ingest disabled in --test.")
                continue
            url = input("YouTube URL: ").strip()
            print("\nSource label:")
            print("  1. Simply Cyber Daily Threat Brief")
            print("  2. Barricade Cyber")
            print("  3. AlienVault OTX")
            print("  4. Other (type manually)")
            src_choice = input("Selection: ").strip()
            if src_choice == "1":
                source_label = "Simply Cyber Daily Threat Brief"
            elif src_choice == "2":
                source_label = "Barricade Cyber"
            elif src_choice == "3":
                source_label = "AlienVault OTX"
            else:
                source_label = input("Source label: ").strip() or "Unknown"
            try:
                content = get_gemini_transcript(url)
                raw_output = analyze_with_claude(content, url, date.today().isoformat())
                write_governance_file(raw_output)
            except (RuntimeError, ValueError) as e:
                print(f"❌ Pipeline failed: {e}")
                continue
            records = parse_records(SCRIPT_DIR / "governance_input.txt")
            print(f"\n📋 Pushing {len(records)} record(s) to Notion...")
            push_all(records, source_label, url)

    # ── Post-run audit ──────────────────────────────────────────
    if CMMC_MISSES:
        print(f"\n{'='*60}")
        print(f"⚠️  CMMC MISS REPORT — {len(CMMC_MISSES)} unresolved ID(s)")
        print(f"{'='*60}")
        for entry in CMMC_MISSES:
            print(f"   ✗ {entry}")
        print("   Check: Claude output format vs Notion control name spelling.")
    else:
        print("\n✅ All CMMC IDs resolved cleanly.")


if __name__ == "__main__":
    main()
