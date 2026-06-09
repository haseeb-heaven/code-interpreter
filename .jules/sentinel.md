## 2024-06-09 - Command Injection Risk in File Openers
**Vulnerability:** Command injection vulnerability existed in Windows file opening fallback because `subprocess.call` was invoked with `shell=True` and unvalidated user input (`filename`).
**Learning:** Even internal helper scripts or file opening fallbacks can become command injection vectors if they use `shell=True` to execute a system command with variable paths.
**Prevention:** Prefer `os.startfile(filename)` on Windows, which directly hooks into the OS file association mechanism without using an intermediate shell, eliminating command injection risks.
