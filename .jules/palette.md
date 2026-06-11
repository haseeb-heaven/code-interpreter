## 2024-06-11 - TUI Keyboard Trap & Options Clarity
**Learning:** TUI environments in raw mode can trap keyboard interrupts (Ctrl-C) if `\x03` is not explicitly handled, and default rich prompts mask available choices without strict matching.
**Action:** Explicitly map `\x03` to exit actions, add shortcut hints to footers, and format string prompts to display options clearly.
