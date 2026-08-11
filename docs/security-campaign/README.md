# Security Principles Campaign — Documentation

This folder is the durable, Git-tracked record of the Security Principles Campaign system (the gamified GRC learning platform built on top of `GRC_Learning_Plan_All_Phases` in Notion).

**Split of responsibility, per standing project rule:** Notion is the live execution cockpit — where lessons actually live, where AO reviews and approves, where the day-to-day work happens. This `docs/` tree is the durable archive — what got decided, what got built, and why, in a form that survives outside Notion and is diffable/reviewable like the rest of the codebase.

## Contents

- `build-log.md` — chronological log of what was actually built, in order.
- `pilot-lessons.md` — the 5 pilot lessons, their final format, and how to extend it to more lessons.
- `../persona-workflow/` — AO/persona routing model and approval-gate rules.
- `../cold-starts/` — one note per major session, for resuming cold.
- `../changelogs/` — dated changelog entries.

## Operating Rule (mirrors the Notion Cold Start Board)

No session ends without a handoff. If the work can't be resumed cold from this folder plus `boards/BOARD.md`, the documentation isn't doing its job yet.

## Current State (as of 2026-08-08)

All 5 pilot lessons are converted and AO-accepted:

- HardOPS Principles
- Week 1 – What is GRC?
- NIST CSF
- Pivot Tables for GRC
- Excel: VLOOKUP

See `build-log.md` for the full history and `pilot-lessons.md` for the format spec.
