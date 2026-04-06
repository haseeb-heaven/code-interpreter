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
