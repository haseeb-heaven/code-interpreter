## 2025-01-01 - TUI Shortcuts and Visual Prompts
**Learning:** In headless terminal environments, web-style visual affordances must be explicitly surfaced (e.g., manually formatting options in `rich` prompts without triggering markup parsing). Furthermore, 'Esc' (`\x1b`) should never be advertised as a TUI cancel action in raw mode, as blocking ANSI escape sequence reads can hang the app.
**Action:** Always manually escape choice formatting in `rich` prompts (e.g., `\[a|b]`), use `\x03` (`Ctrl-C`) for TUI cancellation, and append shortcut hints to footer text.
