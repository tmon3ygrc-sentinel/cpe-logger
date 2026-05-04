# 🦅 STAR CPE Logger

**Threat Intelligence → CMMC 2.0 Gap Analysis — Automated**

A specialized automation engine that ingests daily security threat intelligence, classifies it using analyst-grade extraction, and maps it against **CMMC 2.0 / NIST 800-171** control families in a live Notion GRC repository.

Built as part of the **STAR Project** (Self-Transformation through Adversarial Rigor) — a hands-on vCISO development program emphasizing manual mastery before automation.

## What This Does

- **Classifies** threat stories by type (incident, vulnerability, advisory, strategic)
- **Maps** threats to specific CMMC 2.0 control IDs with live Notion relations
- **Tracks** impacted identity providers and systems
- **Builds** a living compliance gap analysis automatically

Result: A vCISO-grade, always-up-to-date compliance intelligence system with minimal manual effort.

## Architecture

```
YouTube Transcript → filter_dtb_transcript.py → AI Strike Team (Mack / Lyra / Jax)
                    ↓
             governance_input.txt
                    ↓
             notion_logger.py (v5.0)
                    ↓
          Notion GRC Repository
   (CPE Tracker + Master Frameworks)
```

## Quick Start

1. Clone the repo
   ```bash
   git clone https://github.com/tmon3ygrc-sentinel/cpe-logger.git
   cd cpe-logger
   ```

2. Setup environment
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Configure `.env` with your Notion Integration Token and Database IDs.

4. Run
   ```bash
   python notion_logger.py
   ```

## Key Components

- `notion_logger.py` — Core logging engine
- `filter_dtb_transcript.py` — Transcript preparation for AI
- `cmmc_populate.py` — Seeds CMMC controls
- AI Prompt templates (Mack, Lyra, Jax)

## License

MIT License

---

*Built with HardOps discipline. Eat your own cooking.* ⚔️💎🦅
