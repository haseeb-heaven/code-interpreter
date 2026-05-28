## 2024-05-24 - Remove shell=True Vulnerabilities
**Vulnerability:** Use of `shell=True` with `subprocess.call` and `subprocess.check_call` for commands like `start` on Windows, creating command injection risks.
**Learning:** Even with argument validation, using `shell=True` on Windows allows the underlying command processor (`cmd.exe`) to interpret shell metacharacters, potentially leading to command injection.
**Prevention:** Avoid `shell=True` entirely. Use `os.startfile(filename)` for opening files on Windows, and resolve executables using `shutil.which` to safely execute them without shell resolution.
