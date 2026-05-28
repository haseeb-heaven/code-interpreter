## 2024-05-28 - Avoid keyboard traps in TUI raw mode
**Learning:** In terminal UIs using raw mode, standard interrupts like Ctrl-C (`\x03`) do not trigger `KeyboardInterrupt` automatically, creating a keyboard trap.
**Action:** Always map standard interrupt bytes (e.g., `\x03`) to exit/cancel actions and explicitly document shortcuts like 'Esc/Ctrl-C to cancel' to improve accessibility.
