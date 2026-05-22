## 2025-05-24 - Command Injection Vulnerability in Utility Manager
**Vulnerability:** The `_open_resource_file` function used `subprocess.call(['start', filename], shell=True)` on Windows. If `filename` contains shell metacharacters, it could lead to arbitrary command execution.
**Learning:** Invoking the shell with `shell=True` and user-controlled input (even partially, like file paths) introduces command injection risks. On Windows, `os.startfile()` provides a safer alternative for launching files with their default associated applications.
**Prevention:** Avoid `shell=True` whenever possible. When launching or opening files on Windows, prefer using `os.startfile(filename)` over `subprocess.call(['start', filename], shell=True)`.
