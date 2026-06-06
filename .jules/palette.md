## 2025-01-01 - Terminal UI Accessibility
**Learning:** When falling back to headless or text inputs from TUI, explicit prompt choices help users, and avoiding keyboard traps (by explicitly handling Ctrl-C /  in raw TTY mode) prevents user frustration.
**Action:** Explicitly bind interrupt bytes like  to exit actions in raw terminal interfaces and surface keyboard shortcuts clearly in instructions.
