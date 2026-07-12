# Live Interactive + Agentic Media Suite — Design

**Date:** 2026-07-12  
**Branch:** `test/worktree-live-interactive`  
**Owner:** AGENT LIVE  
**Status:** Approved (Approach A)

## Goal

Ship discoverable live tests for Open Code Interpreter covering:

1. **Agentic media/data** under `tests/agentic/media/` (Approach A)
2. **Interactive live matrix** under `tests/live/` — providers from `.env`, free LLMs, sandbox/stream, python/js/r soft-skip

Reports under gitignored `scratch/`. Fixtures via `INTERPRETER_TEST_DATA_DIR` (alias `TEST_DATA_DIR`); never hardcode `D:\tmp`.

## Soft-skip (never hard-fail)

- Billing / quota / rate-limit / auth
- Missing deps (ffmpeg, node, Rscript, local endpoint down)
- Missing/placeholder API keys

Never print or commit secrets.

## Success criteria

- Offline unit tests pass without live keys
- Live run produces PASS/SKIP/FAIL table with zero hard FAIL
- `scratch/` in `.gitignore`
- Push `test/worktree-live-interactive` only when live green
