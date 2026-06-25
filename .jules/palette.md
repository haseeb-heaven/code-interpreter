## 2025-05-18 - Improve terminal UI affordances
**Learning:** In terminal UI (TUI) environments, explicit prompts (e.g., choices, hint texts) are critical for intuitive UX because mouse affordances are missing. Explicitly raising KeyboardInterrupt on `\x03` prevents keyboard traps during raw input mode.
**Action:** Always include keyboard hint strings (like Esc to cancel) and format option choices inline for headless prompt inputs. Handle interrupt signals directly.
