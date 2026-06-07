## 2024-05-24 - Handle Ctrl-C correctly in Terminal UI raw mode
**Learning:** In terminal raw mode (e.g. using `tty.setraw()`), the `SIGINT` signal (Ctrl-C) is not raised as a `KeyboardInterrupt` by the terminal. Instead, the raw `\x03` byte is passed directly to standard input. This creates a keyboard trap where users cannot intuitively exit the prompt.
**Action:** Explicitly map the `\x03` byte alongside standard exit sequences (like 'escape') to trigger cancellation, and provide explicit hints in the UI ("Esc/Ctrl-C to cancel") to guide the user.
