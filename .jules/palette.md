## 2024-06-22 - TUI Keyboard Trap Fix
**Learning:** When building terminal UIs with explicit raw mode reading (like bypassing `rich` prompt and using `tty.setraw`), standard interrupt combinations like Ctrl-C (`\x03`) do not raise `KeyboardInterrupt` by default. This causes a severe keyboard trap that prevents users from cleanly escaping out of selection states.
**Action:** Always intercept `\x03` explicitly when parsing raw keystrokes in terminal interactions and manually raise `KeyboardInterrupt` to preserve accessible escape hatches.
