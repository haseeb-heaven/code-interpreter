## 2024-05-24 - Interactive TUI Keyboard Traps
**Learning:** In raw terminal mode, standard interrupt bytes like `\x03` (Ctrl-C) and `\x04` (Ctrl-D) are captured rather than raising exceptions, trapping users in the interactive prompts unless explicitly handled.
**Action:** Map standard interrupt characters to KeyboardInterrupt or exit sequences in all raw terminal inputs, and clearly label the cancellation shortcuts (like "Esc/Ctrl-C to cancel") on screen.
