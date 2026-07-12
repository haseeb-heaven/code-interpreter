# Unit Coverage ≥80% Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. Steps use checkbox syntax.

**Goal:** Raise unit-test coverage of `libs/*` + `interpreter.py` to ≥80% on branch `test/worktree-unit-80`.

**Architecture:** Measure baseline with pytest-cov over unit tests (exclude live/smoke/heavy e2e). Add focused unit tests for the largest miss gaps (data/, core/main_loop, code_interpreter, utility_manager, agents, tools). Prefer pure unit tests with mocks; no live LLM.

**Tech Stack:** Python 3.12, pytest + coverage.py, D:\henv\Scripts\python.exe, unittest-compatible tests under `tests/`.

---

### Task 1: Baseline coverage

- [ ] Run coverage on unit suite scoped to `libs` + `interpreter.py`
- [ ] Rank modules by Miss count; pick top gaps

### Task 2: Fill high-miss modules (TDD)

- [ ] Write failing tests for uncovered behaviors in top-gap modules
- [ ] Confirm RED (misses / failing assertions)
- [ ] GREEN via tests only (no production changes unless bug)
- [ ] Repeat until TOTAL ≥80%

### Task 3: Verify + ship

- [ ] Full unit discover pass
- [ ] Fresh coverage report ≥80%
- [ ] CHANGELOG note, commit, push `test/worktree-unit-80`
