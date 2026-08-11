# Approval Gates & Standing Discipline

These rules were established (several the hard way, via real mistakes) over the course of the Security Campaign and Malware Compendium build sessions. They apply project-wide, not just to the Security Campaign.

## Hard Rules

1. **Never use a full-page `replace_content` unless the original content has already been captured/restored and the replacement explicitly includes it.**
   Established after Week 1 – What is GRC?'s original OCEG content (definition breakdown, LEARN/ALIGN/PERFORM/REVIEW deep dive, Interview Pitches, VW emissions case study) was overwritten by an early conversion pass. AO caught it; content was restored verbatim from a prior fetch capture in the same session, not reconstructed from memory.

2. **Verify every write via a fresh fetch/query immediately after — never trust the write call's own echoed response.**
   Caught a real bug this way: a `notion-create-pages` call that omitted the `parent` argument silently produced 9 empty-title standalone pages instead of erroring. Only caught because the very next step was a live verification fetch, not because the tool complained.

3. **Approval is per-action, never blanket.** A prior "yes" does not authorize a later, different action — even a closely related one. When a new action conflicts with a standing instruction (e.g. a pause), flag the conflict explicitly and get an explicit new decision.

4. **Flag mistakes and gaps honestly, don't hide or gloss over them.** Examples: the destructive-replace mistake above; a duplicate-row bug found during a later CMMC audit (see `boards/BOARD.md`, 2026-08-08 entries); a cosmetic label typo on the VLOOKUP page, self-flagged even though it didn't affect underlying data.

5. **No fabricated facts, figures, or timelines.** Any real-world claim (incident dates, dollar figures, record counts, citations) must be independently verified via search before being written — never drafted from training-data memory alone, even when it feels confidently known.

6. **If a tool can't safely perform an action (e.g. recreating a Notion `<unknown>` block), don't fight it — document the limitation and route around it or flag for manual action.**

## Notion-Specific Operational Notes

- `<page url="...">Title</page>` and `<database url="..." inline="true">Title</database>` block tags must be preserved verbatim in content edits — the API will refuse edits that would silently delete child pages/databases, and returns an explicit error naming what would be lost. Treat that error as a safety net, not an obstacle to route around.
- There is no delete tool via the Notion MCP connector. The established pattern for junk/duplicate rows is: rename to `DELETE-ME-<reason>` with a Change Notes explanation, and flag for manual deletion in the Notion UI.
- Large page fetches (~69K+ chars) get saved to a local file instead of returned inline — read via targeted `bash`/grep slicing or delegate to a subagent, never guess at unread content.
