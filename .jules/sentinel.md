## 2024-05-20 - Command Injection via subprocess.call on Windows
**Vulnerability:** `subprocess.call(['start', filename], shell=True)` allows command injection even if `os.path.isfile()` passes because Windows filenames can legally contain shell metacharacters like `&` and `^`.
**Learning:** Checking file existence is insufficient to prevent command injection when using `shell=True` on Windows for file opening.
**Prevention:** Use `os.startfile(filename)` on Windows to securely launch files instead of executing `start` through a shell.
