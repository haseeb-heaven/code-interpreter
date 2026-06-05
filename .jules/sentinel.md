## 2025-06-05 - Command Injection via subprocess.call with shell=True
**Vulnerability:** Use of `subprocess.call(['start', filename], shell=True)` for opening files on Windows.
**Learning:** Even when invoking the shell with a list of arguments, `shell=True` can evaluate special characters in the filename, allowing command injection on Windows.
**Prevention:** Use `os.startfile(filename)` when opening files on Windows to avoid invoking the shell entirely.
