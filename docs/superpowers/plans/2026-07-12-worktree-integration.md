# Worktree Integration Tests Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen mocked integration coverage under `tests/integration/` (CLI flag wiring, pipelines, session/output/tools/agents) toward overall ≥80% when merged.

**Architecture:** Add focused unittest modules that exercise real `build_parser`/`prepare_args`/`main` routing and stubbed AgentPipeline / AutoLoop / OutputFormatter / ToolRegistry collaborators—no live LLM providers.

**Tech Stack:** Python 3.10+/unittest, unittest.mock, `D:\henv\Scripts\python.exe`

---

### Task 1: CLI flag wiring integration

**Files:**
- Create: `tests/integration/test_cli_flag_wiring.py`

- [x] **Step 1:** RED — assert `--gemini-style` implies agentic+free+cli+stream; JSON disables stream; session forces CLI; yolo+yes forces autonomy; main routes agentic/auto.
- [x] **Step 2:** GREEN — run suite; fix assertions against real `prepare_args`/`main` contracts only.
- [x] **Step 3:** Commit when green with other tasks.

### Task 2: Agent pipeline path coverage

**Files:**
- Create: `tests/integration/test_pipeline_paths.py`

- [x] **Step 1:** RED — safety-blocked path skips execute; error+safe triggers repairer; async `run_async` completes with stubs.
- [x] **Step 2:** GREEN — verify against `AgentPipeline`.

### Task 3: Tools + session + output integration

**Files:**
- Create: `tests/integration/test_tools_session_output.py`
- Create: `tests/integration/test_mainloop_slash_commands.py`

- [x] **Step 1:** RED — registry/search, OutputFormatter, SessionStore, AutoLoop yolo, `/tools` `/memory`.
- [x] **Step 2:** GREEN — verify offline.

### Task 4: Verification + push gate

- [x] Run `python -m unittest discover -s tests/integration -v` — green (25/25).
- [x] Push `test/worktree-integration` only with fresh green evidence.
