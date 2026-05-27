## 2025-05-27 - Translating Web UX to Terminal
**Learning:** Web-specific UX concepts (like explicit affordances and keyboard traps) translate directly to terminal UI: show choices explicitly in prompts, provide clear shortcut hints, and map interrupt bytes (`\x03`) to cancel/exit to prevent trapping users in raw mode.
**Action:** Always add `\\[{'|'.join(options)}]` to rich prompts, add "Esc/Ctrl-C to cancel" hints to selector footers, and ensure raw mode reads explicitly catch `\x03`.
