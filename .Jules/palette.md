## 2025-05-09 - TUI Keyboard Traps
**Learning:** Terminal applications using raw mode often suppress system interrupts like `Ctrl-C` (`\x03`), causing keyboard traps where users can't easily exit menus. Additionally, omitting explicit choices in text prompts reduces discoverability.
**Action:** Always map standard interrupt bytes (like `\x03`) to exit actions in raw mode TUI components, update footer text to advertise exit shortcuts (e.g. "Esc/Ctrl-C to cancel"), and always pass valid options to prompt libraries to ensure they are visible.
