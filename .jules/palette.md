## 2025-06-10 - Improved TUI prompt UX for headless environments
**Learning:** Using `Prompt.ask` without options makes it unclear what choices the user has in non-interactive mode. However, passing `choices` to rich's `Prompt.ask` makes it case-sensitive, which breaks existing case-insensitivity handling.
**Action:** Manually format choices into the prompt text with escaped brackets `\\[choice1|choice2\\]` to display available options while preserving custom case-insensitive input parsing.
