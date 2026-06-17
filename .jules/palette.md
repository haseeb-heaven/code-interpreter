## 2025-06-17 - TUI Keyboard Interaction
**Learning:** Raw terminal reading mapping Esc but swallowing Ctrl-C (\x03) results in a keyboard trap, making users feel stuck. Similarly, `rich` parses brackets in prompts as markup causing errors unless escaped.
**Action:** When implementing custom raw input reading, explicitly raise `KeyboardInterrupt` for \x03. Always escape brackets when injecting choices into `rich` Prompts.
