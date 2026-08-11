# Cold Start — Pilot Lesson Conversion / "FORGE Academy" (2026-08-08)

Mirrors the Notion cold-start note ("Pilot Lesson Repair — Non-Destructive Wrapper Normalization", Security Campaign Cold Start Board) and `boards/BOARD.md` entries dated 2026-07-25 through 2026-08-08.

## What Changed

All 5 pilot lessons (HardOPS Principles, Week 1 – What is GRC?, NIST CSF, Pivot Tables for GRC, Excel: VLOOKUP) went from a rough first-pass conversion through several real iterations to a final, AO-accepted state:

1. **Pass 1 (destructive):** direct property update + full content replace. Too destructive — overwrote Week 1 GRC's real original OCEG content.
2. **Pass 2 (repair):** AO caught the content loss, set the standing non-destructive rule, content restored verbatim.
3. **Pass 3 (FORGE spec):** formal wrapper structure (`# Security Mission Wrapper` → Mission Brief/AO Intent/Persona Route table/Mission Tasks/Evidence Required/Completion Gate → `# Original Lesson Content` → `# Mission Notes / Evidence Log`). AO then set a standing pause pending visual review.
4. **Pass 4 (RPG restyle):** AO lifted the pause specifically to backport a more polished RPG-style presentation (already in use on the SOC 2 Trust Services Criteria page) into 3 of the 5 lessons. The other 2 (Pivot Tables, VLOOKUP) were checked and found to already exceed that style — deliberately left untouched rather than downgraded. AO accepted on visual review ("wrappers are good").
5. **Pass 5 (NIST CSF content-parity):** separate AO request — bring NIST CSF up to SOC 2's actual *teaching depth*, not just its header. Rebuilt with a table of contents, Beginner Translation table, CSF map, Field Scenario, practice mapping table, and a Deep Dive with one real sourced incident per Core Function (Equifax, Colonial Pipeline, Marriott/Starwood, Uber, Maersk/NotPetya) plus 5 secondary references. AO satisfied with the result, then manually deleted the now-superseded Original Lesson Content section directly in Notion (own action, not agent-initiated) — this also moved 3 child pages to Notion Trash (recoverable, not hard-deleted), including one holding a real `.xlsx` attachment and a completed practice deliverable.

## Adjacent Work (same session, different system — Master Frameworks CMMC DB)

Not part of the Security Campaign, but done in the same session: a completeness audit of the `Master Frameworks (CMMC 2.0/NIST 800-171)` Notion DB, prompted by a recurring pipeline warning (`SR.L2-3.15.2` unresolved CMMC ID). Found and fixed 4 genuinely missing L2 rows, 1 mislabeled row, 1 data bug, and consolidated a duplicate row (the earlier "fix" for the recurring warning had created a duplicate rather than filling a real gap). A bigger Rev 3 family-numbering mislabeling (SR/SA/PL) was found but explicitly parked — AO decision: hold, Rev 2/CMMC 2.0 only for now. The actual root cause of the original 4x-recurring pipeline warning is still open — two hypotheses tested and ruled out (Control Status filter, emoji-polluted Name field); next step is a runtime debug trace in `load_cmmc_cache()` (`notion_logger_v7.py`), not yet done. See `boards/BOARD.md` for full detail — this system has its own documentation track, not this one.

## Current State

- All 5 pilot lessons: **closed, AO-accepted.**
- Security Campaign Cold Start Board (Notion): 3 of 4 entries now Resolved; only the Git/VSCode Documentation Plan entry remains open — closed by this very cold-start note and the folder structure it lives in.
- One small open item: a `DELETE-ME-duplicate-row (was SR.L2-3.15.2)` row in the Master Frameworks DB still needs manual deletion in the Notion UI (no delete tool via the connector).

## Next Actions

- None blocking for the Security Campaign. Malware Compendium tranche 3 remains separately gated pending AO go-ahead (see `boards/BOARD.md`).
- If revisiting the CMMC root-cause trace: add a temporary debug print to `load_cmmc_cache()` dumping every SR.L2-3.15.x cache key at runtime, compare byte-for-byte against the pipeline's lookup string.
