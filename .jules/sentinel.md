## 2024-05-24 - Command Injection via subprocess.call on Windows
**Vulnerability:** Command injection when opening files on Windows using `subprocess.call(['start', filename], shell=True)`.
**Learning:** Using `shell=True` with unvalidated input on Windows can lead to command injection. `os.path.isfile()` check is insufficient to prevent command injection because Windows filenames can legally contain shell metacharacters like `&` and `^`.
**Prevention:** Use `os.startfile(filename)` instead of `subprocess.call` when opening files on Windows.
