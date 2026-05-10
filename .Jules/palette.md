## 2026-05-10 - TUI Keyboard Trap Resolution
**Learning:** Raw terminal mode blocks standard interrupt signals (`` / Ctrl-C), which can inadvertently trap users in TUI menus if not explicitly handled alongside `escape`.
**Action:** When implementing raw mode input capture for terminal UIs, always explicitly map the `` byte to an exit/cancel action and provide clear on-screen hints like '(Esc/Ctrl-C to cancel)' to prevent keyboard traps.
