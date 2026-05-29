## 2024-05-29 - TUI Keyboard Traps and Discoverability
**Learning:** In terminal environments, raw input modes can swallow standard OS interrupt signals (like `\x03` for Ctrl-C), trapping users. Additionally, TUI elements without explicit shortcut hints and non-TTY prompts without explicit choices leave users guessing.
**Action:** Always map standard interrupt bytes to exit actions in raw mode, explicitly render cancel shortcuts (e.g., 'Esc/Ctrl-C to cancel'), and format choices directly into non-TTY prompts avoiding strict validation pitfalls.
