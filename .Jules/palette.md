## 2024-05-14 - Handle Ctrl-C gracefully in TUI keyboard traps

**Learning:** In terminal UI (TUI) environments like this repository, web-specific UX concepts translate to terminal equivalents such as avoiding keyboard traps by mapping standard interrupt bytes (`\x03`) to exit actions in raw mode.
**Action:** Always intercept standard termination characters in raw input handling.
