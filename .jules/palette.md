## 2024-05-24 - Translating Web UX to Terminal UI
**Learning:** In terminal UIs, web UX concepts translate to explicit text formats: missing visual choices (dropdowns) require manual prompt choices (e.g., `\\[a|b|c]`), implicit escape actions need explicit visual hints ('Esc/Ctrl-C to cancel'), and handling keyboard traps requires raising exceptions for interrupt bytes (`\x03`) in raw mode.
**Action:** Always provide explicit visual choices, explicit escape hints, and map standard interrupt bytes appropriately in TUI apps to maintain an intuitive and accessible UX.
