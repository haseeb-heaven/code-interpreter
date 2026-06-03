
## 2024-05-24 - Explicit Prompt Choices and Raw Mode Interruption
**Learning:** When using raw terminal mode, standard interrupts (like Ctrl-C) do not trigger KeyboardInterrupt and must be manually mapped. Furthermore, when providing prompt options via `rich.Prompt.ask()`, escaping brackets (e.g. `\[a|b]`) is required to avoid markup parsing issues while effectively conveying choices.
**Action:** Explicitly map `\x03` to exit actions in raw mode readers and manually format explicit prompt choices for fallback UIs to enhance accessibility.
