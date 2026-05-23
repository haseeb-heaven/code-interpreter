## 2025-03-09 - Avoid Command Injection with `shell=True` in subprocess calls
**Vulnerability:** Command injection via `subprocess.call` with `shell=True` in file-opening logic.
**Learning:** Using `shell=True` to execute a command with a user-influenced filename creates a critical risk, especially on Windows, where standard shell capabilities are invoked.
**Prevention:** When launching or opening files on Windows, prefer using `os.startfile(filename)` over `subprocess.call(['start', filename], shell=True)` to avoid potential command injection vulnerabilities.
