## 2024-05-18 - Display explicit options in headless TUI prompts
**Learning:** Headless fallback prompts relying on default fallback behavior without displaying options can trap users. Showing choices explicitly improves accessibility and usability in non-TTY environments.
**Action:** When creating text-based prompts that fallback to standard input matching, always format the available options visibly within the prompt string.
