## 2025-05-18 - Prevent Command Injection on Windows File Open
**Vulnerability:** `subprocess.call(['start', filename], shell=True)` allows command injection on Windows because filenames can legally contain shell metacharacters like `&` and `^`.
**Learning:** Checking `os.path.isfile()` is insufficient to prevent shell injection when `shell=True` is used.
**Prevention:** Always use `os.startfile(filename)` to open files on Windows instead of invoking `start` through a shell.
