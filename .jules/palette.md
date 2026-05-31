## 2024-05-31 - Avoid terminal keyboard traps
**Learning:** In terminal UIs running in raw mode, standard interrupts like Ctrl-C (`\x03`) are often captured as raw input. Without explicit handling and visible hints, users can get trapped in selection loops, leading to a frustrating experience.
**Action:** Always map standard interrupt bytes (`\x03`) to exit/cancel actions and explicitly document shortcuts like "Esc/Ctrl-C to cancel" in the UI footer for discoverability.
