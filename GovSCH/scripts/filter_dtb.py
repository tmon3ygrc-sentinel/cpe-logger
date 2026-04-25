"""
Daily Threat Brief Transcript Filter v2.9 (Star Project Edition)
- Unified Identity: Syncs with Mack, Lyra, and Jax templates.
- Elastic Logic: Handles multi-model chunking and GRC mapping.
- Source of Truth: Pulls prompts directly from local /prompts folder.
"""

import pyperclip
import re
import os
from pathlib import Path

# --- CONFIGURATION & PROFILES ---

INSTRUCTION_PROFILES = {
    "1": {
        "name": "Mack (ChatGPT)",
        "max_chars": 12000,
        "gate_tag": "[END OF TRANSCRIPT - BEGIN GPT ANALYSIS]",
        "template": "cpe_prompt_chatgpt.txt",
        "specifics": (
            "STRICT: Clinical analysis. No markdown filler. INDIVIDUAL RECORDS PER STORY. "
            "Use double-colon keys. CRITICAL: Do NOT use markdown — no ## headers, "
            "no backslash escaping, no backticks anywhere in output."
        )
    },
    "2": {
        "name": "Lyra (Claude)",
        "max_chars": 80000,
        "gate_tag": "[END OF TRANSCRIPT - BEGIN CLAUDE ANALYSIS]",
        "template": "cpe_prompt_claude.txt",
        "specifics": (
            "Focus: High-fidelity vCISO synthesis and deep GRC mapping. "
            "INDIVIDUAL RECORDS PER STORY. CRITICAL: Do NOT use markdown — "
            "no ## headers, no backslash escaping, no backticks anywhere in output."
        )
    },
    "3": {
        "name": "Jax (Gemini)",
        "max_chars": 30000,
        "gate_tag": "[END OF TRANSCRIPT - BEGIN JAX ANALYSIS]",
        "template": "cpe_prompt_gemini.txt",
        "specifics": (
            "Focus: Rapid Execution. Velocity. INDIVIDUAL RECORDS PER STORY. No fluff. Parser-ready output. "
            "EXTRACTION REQUIREMENT: Identify EVERY discrete story including strategic and tooling stories. "
            "A complete episode typically contains 4-8 stories. If your count is below 4, re-scan. "
            "CRITICAL: Do NOT use markdown — no ## headers, no backslash escaping, no backticks anywhere in output."
        )
    }
}

STORY_EXTRACTION_STRATEGY = (
    "STORY EXTRACTION STRATEGY: Before writing any output, identify ALL discrete threat stories. "
    "Each identified story MUST produce a SEPARATE and COMPLETE Intel Record using the START/END tags. "
    "EXTRACTION BIAS: Prefer over-extraction. Missing a story is a failure.\n"
    "COUNT VERIFICATION: After completing all records, append: RECORDS GENERATED: [N] matching STORIES IDENTIFIED: [N]."
)

GAP_FILL_STRATEGY = (
    "GAP FILL MODE: Identify ONLY the stories that were missed in the existing records below. "
    "Focus on: strategic stories, threat actor profiles, and policy/regulatory items. "
    "Produce ONLY new records for missed stories using the standard START/END boundary tags."
)

# --- HELPER FUNCTIONS ---

def load_star_template(template_name):
    """Loads the specific AI template from the /prompts sub-folder."""
    # Maps to: [current_dir]/prompts/[template_name]
    t_path = Path(__file__).parent / "prompts" / template_name
    if t_path.exists():
        return t_path.read_text(encoding='utf-8')
    return f"### vCISO PROTOCOL FALLBACK\n1. Analyze technical risk.\n2. Map Control Domains."

def filter_transcript(transcript_text):
    """Enhanced scrubber to strip timestamps and YouTube metadata."""
    EXCLUDE_PATTERNS = [
        "skip navigation", "subscribe", "simply.io", "discord", "streamed", 
        "months ago", "weeks ago", "days ago", "hours ago", "chillhop", 
        "0.5 cpe", "0.5 ceu", "simplycyber.io", "follow along using"
    ]

    TRUNCATION_ANCHORS = [
        "follow along using the transcript",
        "see what others said about this video",
        "get answers explore topics"
    ]

    lower_text = transcript_text.lower()
    truncate_at = len(transcript_text)
    for anchor in TRUNCATION_ANCHORS:
        idx = lower_text.find(anchor)
        if idx != -1 and idx < truncate_at:
            truncate_at = idx
    transcript_text = transcript_text[:truncate_at]

    lines = transcript_text.split("\n")
    filtered_lines = []

    for line in lines:
        line = re.sub(r'\d+:\d+(:\d+)?', '', line).strip()
        if len(line) < 20: continue
        if any(p in line.lower() for p in EXCLUDE_PATTERNS): continue
        filtered_lines.append(line)

    return "\n".join(filtered_lines)

def find_smart_split_point(text, target):
    """Finds a clean break point (\n\n) for chunking large transcripts."""
    for offset in range(0, 500, 10):
        if text[target+offset:target+offset+2] == '\n\n': return target + offset
    split = text.find('\n', target)
    return split if split != -1 else target

def load_existing_records():
    """Manual input for Gap-Fill mode."""
    print("\n📋 GAP FILL MODE: Paste existing records. Type 'END' on a new line to finish.")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END": break
        lines.append(line)
    return "\n".join(lines)

# --- MAIN MISSION CONTROL ---

def main():
    print("=" * 60)
    print("🛡️  STAR PROJECT: DTB FILTER V2.9 (ELASTIC EDITION)")
    print("=" * 60)

    print("\n🎯 Select Mode:\n  1. Standard Analysis  |  2. Gap Fill")
    mode = input("\nMode (1-2, default 1): ").strip() or "1"

    print("\n📄 Reading from clipboard...")
    transcript = pyperclip.paste()
    if not transcript or len(transcript) < 50:
        print("❌ Error: Clipboard is empty or contains junk data.")
        return

    filtered = filter_transcript(transcript)
    print(f"✓ Filtered to {len(filtered)} characters.")

    print("\n🎯 Select AI Strike Team Member:\n  1. Mack (GPT) | 2. Lyra (Claude) | 3. Jax (Gemini)")
    choice = input("\nSelection (1-3, default 3): ").strip() or "3"
    profile = INSTRUCTION_PROFILES.get(choice, INSTRUCTION_PROFILES["3"])

    prompt_base = load_star_template(profile["template"])
    MAX_CHARS = profile["max_chars"]
    PLATFORM = profile["name"]
    GATE_TAG = profile["gate_tag"]
    SPECIFICS = profile["specifics"]

    if mode == "2":
        existing = load_existing_records()
        header = f"SYSTEM INSTRUCTION: {SPECIFICS}\n\n{prompt_base}\n\n{GAP_FILL_STRATEGY}\n\nEXISTING:\n{existing}\n"
    else:
        header = f"SYSTEM INSTRUCTION: {SPECIFICS}\n\n{prompt_base}\n\n{STORY_EXTRACTION_STRATEGY}\n"

    # --- HARDENED DEPLOYMENT LOGIC (V2.96) ---
    if len(filtered) > MAX_CHARS:
        print(f"🔄 Chunking required for {PLATFORM}...")
        split_point = find_smart_split_point(filtered, len(filtered)//2)
        
        # PART 1: The "Holding Pattern"
        # We give the AI a very specific, low-effort task to prevent full analysis.
        part1 = (
            f"{header}\n"
            f"🚨 ATTENTION: THIS IS PART 1 OF A MULTI-PART TRANSCRIPT. 🚨\n"
            f"DO NOT START ANALYZING YET. DO NOT GENERATE RECORDS.\n"
            f"Simply acknowledge receipt with: 'Part 1 Received. Waiting for Part 2.'\n\n"
            f"--- TRANSCRIPT PART 1 START ---\n"
            f"{filtered[:split_point]}\n"
            f"--- TRANSCRIPT PART 1 END ---"
        )
        
        # PART 2: The "Execution Order"
        part2 = (
            f"--- TRANSCRIPT PART 2 START ---\n"
            f"{filtered[split_point:]}\n"
            f"--- TRANSCRIPT PART 2 END ---\n\n"
            f"FULL TRANSCRIPT RECEIVED. PROCEED WITH ANALYSIS NOW.\n"
            f"{GATE_TAG}"
        )

        pyperclip.copy(part1)
        print(f"✅ PART 1 copied to clipboard.")
        input("👉 Paste into Gemini, WAIT for the 'Part 1 Received' reply, then press [ENTER] here for Part 2...")
        
        pyperclip.copy(part2)
        print(f"✅ PART 2 copied. Final trigger tag is {GATE_TAG}")
        
    else:
        # Single-shot deployment for shorter transcripts
        final_text = (
            f"{header}\n"
            f"--- FULL TRANSCRIPT START ---\n\n"
            f"{filtered}\n\n"
            f"--- FULL TRANSCRIPT END ---\n\n"
            f"{GATE_TAG}"
        )
        pyperclip.copy(final_text)
        print(f"✅ MISSION READY FOR {PLATFORM} (Single-shot clipboard updated).")

    print("\n🤘 Mission Complete. Transition to AI analysis.")

if __name__ == "__main__":
    main()
    