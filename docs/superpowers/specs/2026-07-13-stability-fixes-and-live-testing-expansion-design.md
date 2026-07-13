# Stability Fixes + Live Testing Expansion — Design

**Date:** 2026-07-13
**Status:** Approved (user directive: "continue fixing everything and testing all in")
**Phase:** 1 of 2 (bugs + live-test expansion). UI rebrand to gemini-cli style is a separate,
later brainstorm — it needs its own research pass into gemini-cli's actual source/UX and
shouldn't be rushed into this spec.

## Context

`docs/superpowers/specs/2026-07-12-live-interactive-suite-design.md` already shipped a live
scenario harness (`tests/live/scenarios/`) with 15+ cases across easy/medium/complex tiers,
policy/slash/offline_exec/agentic/search/multimodel categories, PASS/SKIP/FAIL reporting to
`scratch/` in both `.md` and `.html`, and a soft-skip classifier
(`tests/live/scenarios/soft_skip.py`) that treats quota/billing/rate-limit/auth errors as
non-fatal `SKIP` rather than `FAIL` — because live third-party quotas are expected to be flaky,
not a product bug.

That philosophy was never carried into the actual product. Running `python interpreter.py`
interactively and hitting an exhausted key produces a raw Python traceback
(`libs.key_manager.AllKeysExhaustedError`) instead of the same graceful degradation the test
harness already knows how to do. This is bug #1.

Bug #2: the persistent banner (`libs/agent/gemini_ui.py`, merged today in `f2ccb3b`) renders
correctly but wraps/truncates on the user's terminal (`Src=inpu` cut mid-word in their repro),
because width comes from a single, sometimes-wrong source (`console.width`).

Separately, `D:\tmp\dummy_media` is a fixture library (archives/audio/code/data/documents/
images/video — ~35 files) not yet wired into `tests/fixtures/` or `tests/live/scenarios/cases.py`.
The existing suite's fixture set (`tests/fixtures/input/`) only covers json/png/pdf/csv/md/txt —
much narrower than the file-type/action matrix the user wants tested (create, analyze, summarize,
convert, edit — across every file type a user might hand the interpreter).

## Goals

1. The classic `--cli` REPL never crashes with a raw traceback on provider exhaustion — it
   degrades the same way the test harness already expects real-world quotas to behave.
2. Banner and status-line output never wraps/truncates regardless of terminal width detection
   accuracy.
3. `tests/fixtures/` gains committed copies of representative files from each `dummy_media`
   category (one or two per type, not all 35 — committed fixtures should stay small), extending
   `tests/live/scenarios/cases.py` with scenarios exercising convert/analyze/summarize/edit against
   the new types.
4. Run the live suite for real (medium + complex tiers, real provider calls) to surface actual
   bugs beyond the two already found, fix them, and produce a fresh `.md`/`.html` report the user
   can read.
5. No hardcoded paths — `D:\tmp\dummy_media` is a local dev convenience for sourcing fixture
   *content*; test code only ever reads `INTERPRETER_TEST_DATA_DIR`/`TEST_DATA_DIR` (existing
   convention) or the committed `tests/fixtures/` tree.

## Non-goals (explicitly deferred)

- gemini-cli-style visual overhaul (Phase 2, separate spec, needs web research first).
- Copying all ~35 dummy_media files into the repo as committed fixtures (bloats the repo; a
  representative subset is enough to exercise each format's code path).

## Approach

### Bug 1 — graceful provider exhaustion

- Catch `AllKeysExhaustedError` at the classic-REPL generation call site
  (`libs/interpreter_lib.py::_generate_content_with_retries` / `libs/core/main_loop.py`), not
  deep in `model_router`.
- Reuse `tests/live/scenarios/soft_skip.py`'s classification strings as the single source of
  truth for "this is a quota/billing condition, not a code bug" — import/share the constant list
  rather than re-declaring it, so product and test classification never drift apart.
- On catch: print a clean Rich message (provider name, ETA from the existing `earliest_recovery`
  field, and a `/model`/`/free` suggestion), then continue the REPL loop instead of exiting.
- Extend the free-model fallback that already exists for `--agentic`/`--yolo`
  (`fix/agentic-rate-limit-fallback`) to the classic path: on exhaustion, attempt one automatic
  retry against a free/open provider (Groq, Cerebras, OpenRouter free tier, or local, in that
  order of what's configured) before falling back to the clean-message-and-continue behavior.

### Bug 2 — banner/status-line wrapping

- In `libs/agent/gemini_ui.py::render_banner` and `libs/core/session.py::display_session_banner`,
  resolve width as `min(console.width, shutil.get_terminal_size(fallback=(80, 24)).columns)`.
- Force `overflow="crop", no_wrap=True` on every banner/status print call so a wrong width
  reading degrades to a clipped-but-legible line instead of wraparound corruption.
- Manual verification: resize a real terminal narrow/wide and confirm no wrap in either case
  (this is a rendering bug — a screenshot or terminal transcript is the actual proof, not just a
  unit test).

### Live testing expansion

- Add one representative file per `dummy_media` category to `tests/fixtures/input/` (e.g. one
  `.zip`, one `.mp3`, one `.mkv`, one `.xlsx`, one `.sqlite`, one extra source-code language) —
  small enough to commit, broad enough to cover the format matrix.
- Extend `tests/live/scenarios/cases.py` with new `ScenarioCase` entries per category × action
  (convert, analyze, summarize, edit) at easy/medium tiers, following the existing
  `offline_exec`/`classic` case patterns already in the file.
- Run `scripts/run_live_scenarios.py --tier medium --tier complex --all-models` for real against
  the configured providers (Groq/Cerebras/OpenRouter/Gemini/local — whatever `.env` has), fix
  whatever real FAILs surface, re-run until green (SKIP is fine, FAIL is not).
- Final report lands in `scratch/live_scenario_reports/` (already gitignored, already produces
  `.md` + `.html`) — point the user at the latest timestamped file rather than inventing a new
  report format.

## Testing

- Unit tests for both bug fixes (exhaustion → clean continue not traceback; narrow width → no
  wrap) alongside the existing `tests/test_key_manager.py` / `tests/test_gemini_ui.py`.
- Live suite run (medium+complex, real providers) as the acceptance check for the testing-expansion
  goal — this *is* the test, not something separately unit-tested.

## Addendum (user follow-up, same approval)

The user's second message elaborated on the same scope with a few concrete, testable additions
folded into this spec rather than spun into a new one:

- **Key rotation / rate-limit behavior** is itself a scenario to test, not just an incidental bug
  — extend `tests/test_key_manager.py` and add a live scenario that forces rotation across a
  multi-key pool and asserts the rotation (not just single-key exhaustion) works.
- **CI/CD on `develop`**: `.github/workflows/ci.yml` currently runs `scripts/run_ci_unit_tests.py`
  plus a coverage gate fixed at `--cov-fail-under=60` over 5 modules
  (safety_manager/code_generator/llm_dispatcher/history_manager + integration). Before merging,
  replicate these exact CI commands locally as the merge gate (no push to `origin` — that needs
  separate authorization). Raise the coverage bar toward the user's 80% target: widen the
  `--cov=` module set and/or add tests to the modules touched by this work so the *effective*
  coverage of changed code clears 80%, without randomly inflating scope by chasing 80% on
  unrelated legacy modules in this same pass.
- **All modes smoke-tested**: `--cli`, `--agentic`, `--yolo`, `--gemini-style`, and
  script/command/vision/chat modes each get at least one live scenario exercising a real
  request end-to-end, not just import-time smoke.
- **Structure/logging sanity**: confirm `logs/`, `scratch/`, `tests/` stay within their existing
  conventions (no new top-level sprawl) and that the exhaustion/rotation fix logs structured,
  secret-free messages — this is a hygiene check alongside the bug fixes, not a repo reorg.

## Workflow

Per standing instruction: work in a git worktree/branch, merge to `develop` only once the full
suite (unit + live medium/complex + the replicated CI commands above) is green. No push to
`origin` unless separately requested.
