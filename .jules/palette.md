## 2024-05-18 - TUI Keyboard Traps and Prompt Clarity
**Learning:** In terminal UIs using raw mode, advertising 'Esc' (\x1b) as a cancellation key can create a keyboard trap because the application subsequently blocks on sys.stdin.read(2) waiting for ANSI sequences (like arrow keys). Also, non-interactive fallback prompts must explicitly list valid choices to be accessible.
**Action:** Explicitly advertise and map Ctrl-C (\x03) to KeyboardInterrupt for cancellations, and manually format explicit options directly into the prompt string using escaped brackets (e.g., \[a|b]) for rich Prompts.
