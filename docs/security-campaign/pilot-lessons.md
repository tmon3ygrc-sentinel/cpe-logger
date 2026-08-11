# Pilot Lessons — Format Spec & Status

## The 5 Pilot Lessons

| Lesson | Status | Format | Notes |
|---|---|---|---|
| HardOPS Principles | ✅ Resolved | RPG-style wrapper | XP 50, ARCHITECT (primary) / AUDITOR (secondary) |
| Week 1 – What is GRC? | ✅ Resolved | RPG-style wrapper | XP 25, AUDITOR (primary) / ARCHITECT (secondary). Original OCEG content restored after an earlier destructive-replace mistake. |
| NIST CSF | ✅ Resolved | RPG-style wrapper + full SOC 2 content-parity | XP 30, AUDITOR (primary) / ARCHITECT (secondary). Rebuilt with real sourced incident case studies — see below. |
| Pivot Tables for GRC | ✅ Resolved (untouched) | Already exceeded target style | SCRIBE (primary) / AUDITOR (secondary). Has its own practice datasets, build instructions, analyst-note examples — deliberately left alone rather than downgraded to match a simpler template. |
| Excel: VLOOKUP | ✅ Resolved (untouched) | Already exceeded target style | SCRIBE (primary) / AUDITOR (secondary). Same reasoning as Pivot Tables. |

## Final Format — RPG-Style Mission Wrapper

The format landed on, after several iterations, mirrors the SOC 2 Trust Services Criteria page's presentation:

```
# Security Mission Wrapper
## [icon] TITLE // SUBTITLE
<callout icon="🎮"> Mission unlocked: ... </callout>
<table> Role / Skill / Mechanic / Win Condition / XP / Persona </table>
> AO Intent: ...
<callout icon="⚔️"> HardOPS Rule: ... </callout>
---
## Mission Tasks (3-5 action-verb tasks: Explain/Map/Detect/Apply/Prove)
## Evidence Required
## Completion Gate
---
# Original Lesson Content
(preserved verbatim — never summarized or dropped without explicit AO sign-off)
---
# Mission Notes / Evidence Log
(empty scaffold until a learner attempts the mission)
```

## NIST CSF — Full SOC 2 Content-Parity (extended format)

NIST CSF went further than the other 4 lessons on a later, separate AO request: match SOC 2's actual *teaching depth*, not just its header style. Added:

- Table of contents + toggle-headed sections
- Beginner Translation table (framework term → plain English → analyst question)
- CSF Map (5 Core Functions, definitions, typical evidence)
- Field Scenario (walks a claim through all 5 functions)
- Practice Build control-mapping table
- Deep Dive: one real, independently-sourced incident per Core Function —
  - **Identify** — Equifax (2017)
  - **Protect** — Colonial Pipeline (2021)
  - **Detect** — Marriott/Starwood (discovered 2018)
  - **Respond** — Uber (2016 breach, disclosed 2017)
  - **Recover** — Maersk/NotPetya (2017)
  - plus 5 shorter secondary references (Target, Capital One, SolarWinds, Equifax's disclosure delay, City of Atlanta)
- Mission Tasks with collapsible model answers
- Customer-Facing Summary Template

Every incident fact (dates, dollar figures, record counts) was independently web-searched and verified before writing — none drafted from memory. Full sourcing detail lives in the NIST CSF page's Mission Notes / Evidence Log section in Notion.

## Extending to More Lessons

To convert another lesson into this format:

1. Fetch the lesson's current content in full — never guess at what's there.
2. Never use a full-page `replace_content` unless the original content has already been captured and the replacement explicitly includes it. (This rule exists because of a real mistake — see `build-log.md`.)
3. Draft the RPG wrapper header, preserve everything else below it under `# Original Lesson Content`.
4. If matching SOC 2's deeper teaching style, source real incidents — verify via search, never invent facts, figures, or timelines.
5. Verify the write via a fresh fetch immediately after — never trust the write call's own echo.
6. Log the change to `build-log.md` and the Notion Cold Start Board.
