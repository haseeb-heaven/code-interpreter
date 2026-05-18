## 2025-05-18 - Prevent Keyboard Traps in Terminal Raw Mode
**Learning:** Raw terminal UI modes intercept system-level signals like Ctrl-C (`\x03`), causing unexpected keyboard traps if not explicitly handled as interrupt/escape actions. Additionally, terminal users lack visual UI affordances and rely on discoverability, making explicit shortcut hints essential for intuitive navigation.
**Action:** Always map standard terminal interrupt bytes (`\x03`) to escape/cancel actions when using raw input (`tty.setraw` or `msvcrt`), and explicitly document the exit shortcuts in UI footers.
