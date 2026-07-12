## Unreleased
- feat(providers): add Cerebras (cloud.cerebras.ai, ultra-fast LPU inference) as a fully wired model provider — `cerebras-gpt-oss-120b`, `cerebras-gemma-4-31b`, `cerebras-zai-glm-4.7` in `configs/models.toml` (litellm `cerebras/<model>` dispatch, `CEREBRAS_API_KEY`), `[[default_priority]]` row, and `[[free_catalog]]` entries (Cerebras public endpoints are free, rate-limited); key routing added to `ModelRouter.initialize_client`/`_resolve_api_key_name`, `libs/llm_dispatcher.py::_detect_provider`, and `libs/key_manager.py::PROVIDER_ENV_MAP`; `.env.example`/README updated; new `TestCerebrasProviderConfig` suite in `tests/test_all_model_configs.py`
- feat(tui): Persist no-args wizard answers to `~/.code-interpreter/config.json` (`libs/core/wizard_config.py`); bare `python interpreter.py` skips the wizard and reuses saved settings once one exists; new `--config` flag forces the wizard to (re)run and re-save. Explicit CLI flags still take precedence over both the saved config and the wizard. Never persists API keys/secrets or one-shot `--task`/`-f` text.
- fix(tui): "Configure advanced options?" → **no** now genuinely skips *every* subsequent advanced prompt (session, YOLO, `--yes`, science, interactive-charts, image, attach, MCP), instead of still asking for the session name right after.
- fix(tui): Cancelling a wizard selector (Ctrl+C / Esc) no longer produces an unhandled `KeyboardInterrupt` traceback; `interpreter.py:main()` catches it around `prepare_args()` and exits cleanly with a short `Cancelled.` message.

## v3.5.0 (2026-07-12)
- refactor(config): replace the `configs/` folder's ~70 per-model JSON files (plus `configs/free/catalog.json` and `configs/schema.json`) with a single human-editable `configs/models.toml` registry (`[models."<key>"]` tables, `[[default_priority]]`, `[[free_catalog]]`)
- feat(config): `libs/core/model_registry.py` — cached `tomllib`/`tomli`-backed loader (`ModelRegistry.load/get_model/has_model/list_model_names/default_model_name/free_catalog_entries`); adds `tomli; python_version < "3.11"` to `requirements.txt`
- refactor(models): `libs/free_llms.py`, `libs/utility_manager.py`, `libs/core/model_router.py`, `libs/core/session.py`, `libs/interpreter_lib.py`, `libs/core/main_loop.py` now resolve models via `ModelRegistry` instead of `configs/<name>.json` paths; `/model`, `--free`, `--list-free`, `--gemini-style`, `-m <model>` behavior is unchanged end-to-end
- chore(scripts): `scripts/smoke_all_models.py`, `scripts/config_builder.sh`/`.bat` updated to read/append `configs/models.toml` instead of per-model JSON files
- docs: README/AGENTS.md updated to document the `configs/models.toml` registry and how to add custom models/providers without touching Python code

## v3.4.0 (2026-07-12)
- fix(agentic/yolo): AutoLoop treats malformed tool XML (`<write_file` / `</function>`) as repairable failure and retries (cap 8) instead of exiting; skip OpenRouter free early when tools unsupported; require real tool_calls for chart/file tasks
- fix(agentic/yolo): AutoLoop OR `RateLimitError` (`free-models-per-day` / `Provider returned error`) jumps to Groq/Gemini immediately without burning sibling OpenRouter `:free` slots; pass config basename into AutoLoop
- feat(ux): Gemini-style step UX for ReAct/agentic + YOLO AutoLoop — Thinking/Executing/Searching spinners and Thought→Action→Observation panels (`libs/agent/step_ui.py`)
- feat(agentic): Missing-binary recovery (ffmpeg, etc.) — detect PATH failures, optional web search, ask before winget/choco/apt/brew install (yolo+yes auto-approves; yolo alone still asks)
- fix(agentic/yolo): AutoLoop free-catalog fallback on `free-models-per-day` / OpenRouter 429 / Stealth 502 (skip remaining OR free → Groq/Gemini/HF); `/model` and settings-like slash commands open TUI pickers; resolve `configs/<name>.json` basenames (e.g. `gemini-2.5-flash`)
- fix(live-session): parse OpenRouter retry-after (cap 60s); skip daily free-quota models; YOLO tool_use_failed repair; REPL paste/slash guards; `.json` not vision; sandbox HOME/MPLCONFIGDIR/Plotly; user-intent absolute writes; neutralize tkinter.mainloop; short litellm errors
- test(fixtures): committed `tests/fixtures/` inputs/expected as live-scenario source of truth (`INTERPRETER_TEST_DATA_DIR` workdir copy)
- test(live): easy/medium/complex scenario suite + master `scratch/live_scenario_report.md|.html` (FAIL=0 soft-skip)
- fix(agentic): Free-LLM resilience — drop dead OpenRouter `:free` catalog IDs; treat 429/RateLimitError as routing failure with capped sleep/retry then catalog fallback; keep controller+specialist models in sync after fallback; `/model` lists presets; suppress rate-limit traceback dumps
- test(unit): raise `libs/*` + `interpreter.py` coverage to ≥80% (worktree unit suite); make data/output/context/local unit modules discoverable under `unittest discover -s tests`
- test(integration): expand mocked CLI/pipeline/tools/session coverage (25/25 worktree integration suite)
- test(live): provider × mode × language matrix + agentic media suite with soft-skip (FAIL=0)
- test(interactive): slash commands, REPL loop, session round-trip, live exec, streaming, -f prompt coverage (#226)
- feat(security): subprocess/Docker sandbox backends, `--timeout`/`--safety` levels, audit log, secret scan, path ignore (#225)
- test(ci): Matrix CI (3 OS × 3 Python), critical-module coverage ≥60%, Codecov badge, shared pytest fixtures (#224)
- feat(science): NumPy/SciPy prompting, notebook export, plot themes, ML helpers, PDF reports, auto-install (#223)
- feat(data): analysis engine with smart ingest, Auto-EDA, chart gallery, multi-format export, SQL, clean (#222)
- feat(local): file attach context (`--attach` / `/file`) + Ollama/`--local` first-class support (#221)
- feat(ux): identity repositioning + first-run onboarding as free/local code interpreter (#220)
- feat(session): Persistent `--session` / `--list-sessions` / `--delete-session` / `/session` across runs (#218)
- feat(output): Structured `--output-format json|markdown|plain` with non-TTY auto-JSON (#219)
- feat(codegen): `--mode generate` snippet + `--mode project` scaffold without execution (#212)
- feat(tools): Native FS/shell ToolRegistry tools + `--yolo` autonomous tool loop + MCP stdio client (`--mcp-server`) (#215)
- feat(ux): Token streaming (`--stream` / `--no-stream`) + multimodal `--image` / `/image` input (#216)
- feat(tools): Web search tool `--search` / `/search` (DuckDuckGo / Tavily / Serper) (#217)
- docs: OSS comparison table (Open-Interpreter, Aider, OpenCode, Gemini CLI, Cline)
- docs: README sections for data analysis, science mode, Ollama/local attach, sandbox levels, sessions, output formats
- test: Expanded unit/integration/interactive coverage; live soft-skip for quota/rate-limit providers

## v3.3.0 (2026-07-11)
- feat(agentic): Gemini-CLI-style `--gemini-style` ReAct REPL with free/cheap LLM catalog (`--free`, `--list-free`, `/free`)
- feat(resilience): Multi-key rotation, token-bucket rate limiter, circuit breaker, error classifier, jitter backoff (`libs/key_manager.py`, `libs/rate_limiter.py`)
- feat(observability): `logs/metrics.jsonl` plus `/key-status`, `/reload-keys`, `/metrics` CLI commands
- feat(ci): Non-interactive `--yes` / `INTERPRETER_YES` one-shot file mode for scripted e2e
- feat(agents): Multi-agent pipeline (`--agent`) and ReAct `--agentic` coder/executor/reviewer/debugger loop
- docs: Fresh CLI screenshots for help, free catalog, code/chat modes, gemini-style, and agentic runs
- test: Resilience smoke suite, mode e2e harness, live soft-skip for quota/rate-limit providers

## v3.2.3 (2026-07-11)
- fix(security): Resolved command injection vulnerability in file opening (`os.startfile`) on Windows.
- fix(security): Mitigated Path Traversal vulnerability in `UtilityManager.get_full_file_path` with strict boundary checks.
- fix(stability): Added timeouts to all external `requests.get` calls in PackageManager and UtilityManager to prevent hangs.
- feat(performance): Optimized `ExecutionSafetyManager` by pre-compiling all regex patterns.
- feat(ux): Improved Terminal UI fallback prompts with explicit choice brackets for non-TTY environments.
- fix: Resolved Ollama/local model API Key extraction and output parsing, updated legacy model configurations.
- chore(models): Updated legacy model configs to 2026 stable aliases (e.g. `gpt-4.1`, `claude-sonnet-4-6`).
- test: Expanded unit test coverage to **263 tests**, validating security fixes, UX enhancements, and API-key robustness.

## v3.2.2 (2026-04-07)
- feat(security): Introduced **secure code sandboxing (enabled by default)** with `/sandbox` and `/unsafe` toggles; replaced `--unsafe` with `--sandbox` / `--no-sandbox`
- feat(security): Strengthened execution safety with subprocess isolation, watchdog fixes, and process-group termination on timeout
- fix(safety): Eliminated multiple safe-mode false positives and blocked new unsafe patterns (write bypasses, absolute-path escapes, destructive commands)
- feat(reliability): Increased SAFE mode timeout to **300s** for long-running tasks; improved Python detection via `ast.parse`
- chore(release): Refined build/release pipeline (`build_release.sh`) with robust error handling and cleaner scripts
- Update interpreter: fix _execute_generated_output language usage, restore sandbox toggle alias, add subprocess security delegation, and increase SAFE mode MAX_TIMEOUT to 300s for more robust long‑running code execution
- fix for watchdog timers issues with sandbox
- fix: clean up spacing/newlines in execute_code() if/else blocks
- fix: temp file exec, /unsafe toggle, build_release.sh update
- Implemented /sandbox command
- chore: update build_release.sh with gh release fix and cleaner structure
- fix: use temp file for code exec; add /unsafe toggle; update build_release.sh
- feat: enhance build_release.sh with robust error handling
- feat: rename --unsafe to --sandbox/--no-sandbox; sandbox ON by default
- feat: update build_release.sh with robust helpers, add /unsafe toggle, fix unsafe execution timeout
- fix: resolve E999 SyntaxError in _WRITE_PATTERNS — replace malformed ['\""] with ['\"] in single-quoted raw strings
- fix: add missing claude-sonnet-4-6.json config required by TestNewConfigFilesFromPR
- fix: two test failures — os.remove \b boundary + .write( on read-handle
- fix(safety): resolve 3 false-positive bugs in safe-mode pattern matching
- fix(code_interpreter): use safety_manager.unsafe_mode instead of UNSAFE_EXECUTION attr
- fix(security): resolve all P1/P2 audit issues from PR #26
- fix(interpreter): use _kill_process_group on timeout + ast.parse for Python detection
- fix(safety): add system-level destructive commands to safe-mode block list
- fix: block bare .write() calls on file handles in safe mode
- fix: allow read-only absolute path access in safe mode
- fix(security): P0 absolute-path read escape + artifact export symlink escape
- fix(safety): expand write-mode detection — close binary/pathlib/JS bypasses (Bug #2)
- fix(#3 #5): add export_artifacts + unquoted POSIX absolute-path block
- fix(P0): process-group SIGKILL on timeout + Python routing in execute_script


## v3.2.1 (2026-04-07)
- Add mode indicator, strict safe-mode blocking, unsafe confirmations, warnings, and improved safety controls for enterprise-grade execution behavior and user awareness
- Update the Sandbox and Code Execution
- Refactor execution architecture with python-first model, restore bash compatibility for tests, fix decoding bug, enforce output limits, update versioning, and correct gitignore entries for logs and newline compliance.
- Overhaul execution architecture with python-first model, sandboxing, and improved safety controls
- stop tracking history.json
- Removed /shell command and added Code Execution safety
- fix(safety): block unquoted absolute-path del command (e.g. del D:\Temp\*.txt)
- test: add safety checks for quoted wildcard del commands and mocked LLM repair loop for dangerous commands
- fix: block quoted wildcard del commands and add Windows absolute-path delete patterns
- feat: enhance safety manager to block absolute-path deletions in various contexts
- feat: enhance llm_dispatcher to support local endpoints
- refactor: update configuration files to use JSON format
- feat: fixed package manager issues with retry circuit logic
- Update configuration files to use triple backtick separators for code generation
- Merge pull request #24 from haseeb-heaven/feature/sandbox-safety-v3
- chore: update changelog, improve README links, and remove deprecated config files
- Merge branch 'feature/sandbox-safety-v3' of https://github.com/haseeb-heaven/code-interpreter into feature/sandbox-safety-v3
- fix: update model configurations and improve error handling in code execution
- feat: update litellm version and add model normalization utility
- Optimize README: move models to Models.MD, shorten sections
- release: prepare v3.1.0 assets and docs
- feat: Add OpenRouter API support with multiple model configurations
- feat: Introduce execution safety features and self-repair mechanism
- Add configuration files and terminal UI for model selection
- Update LLM catalog to newer models and fix model routing bugs

# Changelog

All notable changes to this project are documented in this file.

## v3.2.0 - April 6, 2026
- Added visual mode indicator in session banner ([SAFE MODE] or [UNSAFE MODE ⚠️])
- Implemented strict safety blocking: dangerous operations are hard-blocked in SAFE MODE
- Added confirmation prompts for dangerous operations in UNSAFE MODE
- Enhanced user awareness of destructive operations with warning messages
- Improved enterprise-level safety and user control

## v3.1.1 - April 6, 2026
- Refactored execution architecture to Python-first model (replacing shell-subprocess as default)
- Enforced 10 KB hard output limit with truncation sentinel
- Minor fixes for timeout handling, output limits, and version alignment.

## v3.1.0 - April 5, 2026
- Added OpenRouter support with multiple paid and free model aliases.
- Added OpenRouter free defaults and switched `OPENROUTER_API_KEY` auto-selection to `openrouter/free`.
- Added safer bounded self-repair retries with a max of 3 repair attempts.
- Improved simple intent detection so tasks like printing files in a directory generate minimal executable code instead of extra tables or charts.
- Expanded TUI documentation and added fresh screenshots for mode selection, model selection, and output flow.
- Added release packaging assets and release notes for the `3.1.0` release.

## v3.0.0 - April 5, 2026
- Added a default execution safety sandbox, dangerous command/code circuit breaker, bounded ReACT-style repair retries after failures, clearer execution feedback, and polished CLI/TUI runtime output.

## v2.4.1 - April 5, 2026
- Removed deprecated PALM model path, added NVIDIA + Z AI + Browser Use providers, added `.env.example`, cleaned project artifacts, and introduced `--cli` / `--tui` startup flows with safer interactive error handling.

## v2.4.0 - April 5, 2026
- 2026 model refresh: stable-first OpenAI/Gemini/Anthropic/Groq/DeepSeek catalog updates, legacy alias remaps, CLI smoke validator, and expanded unit tests.

## Earlier releases
- v2.3.0 - Added Deepseek V3 and R1 models support now. Added OpenAI o1 Models support.
- v2.2.x - Save/Execute commands and scripts, logging fixes, package manager fixes, and command improvements.
- v2.1.x - Claude-3 models, Groq Gemma, prompt file mode, OS detection improvements, GPT-4o, and file opening improvements.
- v2.0.x - Groq support plus Claude-2 additions.
- v1.x - Core interpreter, file analysis, Gemini Vision, interpreter commands, chat mode, and local model support.
