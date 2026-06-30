## 2024-05-24 - Prevent Command Injection on Windows
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` on Windows.
**Learning:** Windows filenames can legally contain shell metacharacters (like `&` and `^`). An `os.path.isfile()` check is insufficient to prevent command injection when `shell=True` is used.
**Prevention:** Use `os.startfile(filename)` instead of `subprocess` with `shell=True` to securely open files on Windows.
