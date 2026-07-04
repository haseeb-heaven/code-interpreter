## 2024-07-04 - Terminal UI Keyboard Traps
**Learning:** In terminal raw mode (TTY), reading standard escape sequences natively intercepts `\x03` (Ctrl-C) as standard text, causing keyboard traps.
**Action:** When handling raw input, explicitly catch the `\x03` byte and raise `KeyboardInterrupt` to ensure users can exit the interface, and update prompt messages to explicitly inform the user of standard exit choices like "Ctrl-C to cancel" rather than "Esc" to prevent sequence hanging.
