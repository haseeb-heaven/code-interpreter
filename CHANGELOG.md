## v3.2.2 (2026-04-07)
- Update interpreter: fix _execute_generated_output language usage, restore sandbox toggle alias, add subprocess security delegation, and increase SAFE mode MAX_TIMEOUT to 300s for more robust long‑running code execution
- Merge branch 'feature/code-sandbox-security-v3' of https://github.com/haseeb-heaven/code-interpreter into feature/code-sandbox-security-v3
- fix for watchdog timers issues with sandbox
- fix: clean up spacing/newlines in execute_code() if/else blocks
- fix: temp file exec, /unsafe toggle, build_release.sh update
- Implemented /sandbox command
- chore: update build_release.sh with gh release fix and cleaner structure
- Update Indentation formatting
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
- fix: apply CodeRabbit auto-fixes
- fix(safety): expand write-mode detection — close binary/pathlib/JS bypasses (Bug #2)
- fix(#3 #5): add export_artifacts + unquoted POSIX absolute-path block
- fix(P0): process-group SIGKILL on timeout + Python routing in execute_script
- fix: apply CodeRabbit auto-fixes
- 📝 CodeRabbit Chat: Add unit tests
- fix: apply CodeRabbit auto-fixes
- Update Version file
- Bump the version to 3.2.1


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
- fix: apply CodeRabbit auto-fixes
- feat: update litellm version and add model normalization utility
- fix: apply CodeRabbit auto-fixes
- fix: apply CodeRabbit auto-fixes
- 📝 CodeRabbit Chat: Generate unit tests for PR changes
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