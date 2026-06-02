## 2024-06-02 - TUI Keyboard Traps and Discoverability
**Learning:** In terminal UIs running in raw mode, handling standard exit bytes like `\x03` (Ctrl-C) is critical to prevent keyboard traps. Additionally, explicit hints (like 'Esc/Ctrl-C to cancel' or listing choices in headless prompts) dramatically improve discoverability and accessibility.
**Action:** Always map standard interrupt bytes to exit actions in raw mode terminal loops and explicitly surface available shortcut hints to users.
