## 2024-05-24 - Improve non-interactive prompt UX
**Learning:** When using `rich` library's `Prompt.ask()` in a non-interactive (non-TTY) environment, providing the `choices` argument enforces strict case-sensitive input matching, breaking our custom case-insensitive fallback logic.
**Action:** To provide clear UX by showing options to the user without breaking existing case-insensitivity, manually format the choices into the prompt string using an escaped bracket (e.g., `f"{title} \\[{'|'.join(options)}]"`) instead of passing the `choices` argument.
