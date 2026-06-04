## 2025-01-01 - TUI Keyboard Traps and Shortcut Hints
**Learning:** In raw terminal modes, failing to map standard interrupt bytes (\x03) creates keyboard traps. Additionally, explicit shortcut hints and visible prompt choices are essential for terminal accessibility, mirroring web micro-UX practices.
**Action:** Always map \x03 to exit actions in raw mode, explicitly render choice options in headless prompts, and display clear exit shortcut hints (e.g., 'Esc/Ctrl-C to cancel') in TUI footers.
