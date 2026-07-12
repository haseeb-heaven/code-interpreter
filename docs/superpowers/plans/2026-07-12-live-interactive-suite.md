# Live Interactive Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Approach A `tests/agentic/media/` plus interactive `tests/live/` matrix with soft-skips and scratch reports.

**Architecture:** Media package (fixtures/soft_skip/cases/runner) + provider matrix (detect/cases/runner); scripts write `scratch/` reports; live opt-in via env.

**Tech Stack:** Python 3.10+, unittest, subprocess CLI, litellm dispatcher, dotenv.

---

## File map

| File | Responsibility |
|------|----------------|
| `tests/agentic/media/soft_skip.py` | Billing/dep + redact |
| `tests/agentic/media/fixtures.py` | Resolve test data dir + fixtures |
| `tests/agentic/media/cases.py` | Media/agentic cases |
| `tests/agentic/media/runner.py` | pick model + run_case |
| `tests/agentic/media/test_media_suite.py` | Offline + optional live |
| `scripts/run_agentic_media_suite.py` | Media live runner |
| `tests/live/provider_detect.py` | Key/runtime detect (names only) |
| `tests/live/matrix_cases.py` | Axis-complete cases |
| `tests/live/matrix_runner.py` | Execute + report |
| `tests/live/test_provider_matrix.py` | Offline + opt-in live |
| `scripts/run_provider_matrix.py` | Matrix CLI |
| `.gitignore` | `scratch/` |
| `.env.example` | Commented `INTERPRETER_TEST_DATA_DIR` |

### Task 1: Gitignore + env example
- [ ] Ensure `scratch/` ignored; commented env example

### Task 2–5: Media suite TDD (soft_skip → fixtures → cases → runner)
- [ ] RED tests → GREEN modules → REFACTOR

### Task 6–8: Live matrix TDD (detect → cases → runner + script)
- [ ] RED tests → GREEN modules → REFACTOR

### Task 9: Live run
- [ ] `$env:INTERPRETER_TEST_DATA_DIR='D:\tmp'`; run both scripts; zero FAIL

### Task 10: Push branch when green
- [ ] Commit (no .env/scratch secrets); push `test/worktree-live-interactive`
