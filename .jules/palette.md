## 2024-05-18 - Display explicit prompt choices in TUI
**Learning:** Explicitly surfacing valid choices within the terminal prompt (e.g. `Mode [code|chat|script|command|vision]`) significantly improves UX and accessibility, especially when headless or non-interactive fallback mode is used.
**Action:** When using `rich` Prompt.ask, explicitly manually format choices into the prompt string and escape markup brackets as `\\[` instead of using the `choices` argument to prevent breaking custom case-insensitivity logic.
