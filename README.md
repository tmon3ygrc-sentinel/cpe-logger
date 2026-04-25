# 🦅 STAR CPE Logger

**Threat Intelligence → CMMC 2.0 Gap Analysis — Automated**

A specialized automation engine that ingests daily security threat intelligence, classifies it using analyst-grade extraction, and maps it against **CMMC 2.0 / NIST 800-171** control families in a live Notion GRC repository.

Built as part of the **STAR Project** (Self-Transformation through Adversarial Rigor) — a hands-on vCISO development program built on manual mastery before automation.

## What This Does

Every day, security practitioners consume threat briefings — podcasts, videos, advisories — and extract actionable intelligence. This tool automates the structured logging of that intelligence into a relational Notion database that:

- **Classifies** each threat story by type (incident, vulnerability, advisory, strategic)
- **Maps** threats to specific CMMC 2.0 control IDs with live Notion relations
- **Tracks** which identity providers are targeted per threat
- **Builds** a living compliance gap analysis — automatically

The result is a vCISO-grade deliverable: a threat intelligence database linked to your compliance framework, updated daily with zero manual data entry.

## Architecture

```text
YouTube Transcript
│
▼
┌─────────────────────┐
│  filter_dtb_        │  Filters, scrubs, and deploys transcript
│  transcript.py      │  to AI strike team with extraction directives
└─────────────────────┘
│
▼
AI Strike Team
(Mack / Lyra / Jax)
│
▼
┌─────────────────────┐
│  governance_        │  Parser-ready intel records
│  input.txt          │  ===INTEL_RECORD_START/END===
└─────────────────────┘
│
▼
┌─────────────────────┐
│  notion_logger.py   │  Parses, validates, scrubs, and logs
│  Logger v5.0        │  records to Notion with live CMMC relations
└─────────────────────┘
│
▼
┌──────────────────────────────────────┐
│  Notion GRC Repository               │
│  ├── CPE Tracker (threat intel)      │
│  └── Master Frameworks (CMMC 2.0)    │
└──────────────────────────────────────┘
```

## Prerequisites

| Requirement        | Version   | Notes                               |
|--------------------|-----------|-------------------------------------|
| Python             | 3.10+     | Earlier versions untested           |
| notion-client      | 2.2.1     | Pinned — v3.x breaks pipeline       |
| python-dotenv      | 1.2.1+    |                                     |
| Notion account     | —         | Free tier sufficient                |

## Setup

1. **Clone the repo**
   ```bash
   git clone [https://github.com/tmon3ygrc-sentinel/cpe-logger.git](https://github.com/tmon3ygrc-sentinel/cpe-logger.git)
   cd cpe-logger
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # Windows Git Bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` with your Notion Integration Token and Database IDs.*

   > **Note:** Never commit `.env` — it is listed in `.gitignore`.

## Usage

1. **Filter transcript**
   ```bash
   python filter_dtb_transcript.py
   ```

2. **Analyze with AI**
   Use the **Mack, Lyra, or Jax** strike team prompts to process the filtered output.

3. **Log to Notion**
   ```bash
   python notion_logger.py
   ```

## License

This project is open source under the MIT License.

---
Built with HardOps discipline. Eat your own cooking. ⚔️💎🦅

