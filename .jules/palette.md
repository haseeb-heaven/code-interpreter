
## 2024-05-24 - Interactive Prompts and TUI UX
**Learning:** Terminal UI (TUI) components in headless environments require explicit inline choices in prompts. Additionally, raw mode keyboard handling must explicitly map standard interrupt bytes (like `\x03` for Ctrl+C) to prevent keyboard traps.
**Action:** Always provide explicit choice options inline for fallback prompts and manually map interrupt signals in TUI raw mode implementation.
