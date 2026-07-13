## 2024-07-08 - Displaying choices in Rich prompts without breaking case-insensitivity
**Learning:** When using `rich.prompt.Prompt.ask()`, providing the `choices` argument enforces strict, case-sensitive input matching which overrides custom case-insensitivity logic. Additionally, to manually format the choices into the prompt string, brackets must be escaped as `\\[` to prevent `rich` from incorrectly parsing them as markup and to avoid Python syntax warnings.
**Action:** When we need to show choices but still allow custom validation (like case-insensitivity), format the choices directly into the prompt string and escape the brackets.
## 2026-07-13 - TUI Cancellation Keyboard Traps
**Learning:** In terminal UIs using raw mode input, standard cancellation via the Escape key (`\x1b`) can cause the application to hang when followed by blocking multi-character reads for ANSI sequences. Standard interrupt bytes like `\x03` (Ctrl-C) are safer for explicit cancellation.
**Action:** Always provide explicit keyboard hints for cancellation (e.g., 'Ctrl-C to cancel') and explicitly raise `KeyboardInterrupt` for `\x03` in raw mode key readers to prevent application hangs.
