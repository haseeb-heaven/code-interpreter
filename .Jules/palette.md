## 2025-05-13 - Preventing Terminal Keyboard Traps
**Learning:** In terminal raw-mode UI implementations (like `libs/terminal_ui.py`), standard shell interrupt signals (like Ctrl-C) are intercepted. If standard interrupt bytes (e.g., `\x03`) are not explicitly mapped to an exit action, users become trapped in the prompt.
**Action:** Always map standard interrupt bytes (e.g., `\x03` for Ctrl-C) to an escape/exit action when implementing raw terminal input loops, and explicitly mention these shortcuts in the prompt's help text.
