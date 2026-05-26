## 2024-05-24 - Handle Ctrl-C in Raw Terminal Modes
**Learning:** Raw terminal modes (via `tty.setraw()`) trap standard interrupts like Ctrl-C (`\x03`), causing users to become trapped in infinite input loops if not explicitly handled.
**Action:** Always map the interrupt byte (`\x03`) to the standard exit action (e.g., 'escape' or cancelling) when reading raw keyboard input.
