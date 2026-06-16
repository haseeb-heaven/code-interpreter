## 2025-05-20 - TUI Accessibility and Keyboard Traps
**Learning:** Terminal UIs can trap keyboard users when standard interrupt bytes (\x03) are caught by raw mode without an explicit exit path, and headless prompts without inline choices lack intuitiveness.
**Action:** Always map \x03 to explicitly raise KeyboardInterrupt in TUI raw mode, include inline choices for text prompts, and provide explicit shortcut hints (Esc/Ctrl-C) in footers.
