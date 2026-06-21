## 2024-05-24 - Handle Terminal Raw Mode Keyboard Traps
**Learning:** When creating terminal UIs with raw mode, `\x03` (Ctrl-C) must be explicitly trapped and raised as `KeyboardInterrupt`, otherwise it creates a keyboard trap where standard interrupt keys are ignored. It's also important to explicitly format choices in `rich` Prompts while escaping markup to avoid fallback issues.
**Action:** Always add explicit keyboard interrupt handling for `\x03` and clear exit instructions ('Esc/Ctrl-C to cancel') in terminal UI raw modes.
