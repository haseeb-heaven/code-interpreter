## 2024-07-08 - Displaying choices in Rich prompts without breaking case-insensitivity
**Learning:** When using `rich.prompt.Prompt.ask()`, providing the `choices` argument enforces strict, case-sensitive input matching which overrides custom case-insensitivity logic. Additionally, to manually format the choices into the prompt string, brackets must be escaped as `\\[` to prevent `rich` from incorrectly parsing them as markup and to avoid Python syntax warnings.
**Action:** When we need to show choices but still allow custom validation (like case-insensitivity), format the choices directly into the prompt string and escape the brackets.

## 2024-07-14 - Preventing Keyboard Traps in Raw Terminal Modes
**Learning:** In terminal UI environments, avoiding keyboard traps requires explicitly raising `KeyboardInterrupt` when standard interrupt bytes (`\x03`) are read in raw mode. Advertising 'Esc' (`\x1b`) as a cancel action causes issues as reading it in raw mode followed by a blocking `sys.stdin.read(2)` for ANSI sequences hangs the application.
**Action:** Always handle `\x03` to raise `KeyboardInterrupt` and provide explicit shortcut hints like 'Ctrl-C to cancel'. Do not advertise 'Esc' for cancellation.
