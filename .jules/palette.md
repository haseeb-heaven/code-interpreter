
## 2025-02-23 - Prevent Keyboard Traps in Terminal UI
**Learning:** Terminal equivalents of web accessibility (like preventing keyboard traps) require mapping standard interrupt bytes (e.g., `\x03` for Ctrl-C) to exit actions in raw mode, and providing explicit visual hints for these shortcuts.
**Action:** Always ensure raw terminal input modes explicitly handle interrupt bytes to prevent keyboard traps, and update TUI prompts to clearly display available choices and cancellation shortcuts.
