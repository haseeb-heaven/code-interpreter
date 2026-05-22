
## 2025-01-23 - Prevent keyboard traps and clarify choices in TUI
**Learning:** In terminal UI environments, web-specific UX concepts translate to explicit prompt choices, clear shortcut hints ('Esc/Ctrl-C to cancel'), and avoiding keyboard traps by mapping standard interrupt bytes (`\x03`) to exit actions.
**Action:** Always map `\x03` to an exit action in raw mode, explicitly list valid input choices in prompt strings, and clearly communicate cancellation shortcuts to users.
