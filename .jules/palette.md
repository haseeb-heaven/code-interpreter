## 2025-05-18 - Improve terminal UI accessibility and fallback inputs
**Learning:** Terminal environments without TTYs require explicit choices in text prompts for intuitive headless usage. In raw mode TTYs, standard interrupt bytes (like `\x03`) must be explicitly handled, and keyboard shortcut hints in UI footers prevent keyboard traps.
**Action:** Always provide explicitly listed options in plain text prompt fallbacks and include cancellation shortcut hints in TUI footers to ensure keyboard accessibility.
