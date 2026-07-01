## 2025-01-01 - Command Injection via subprocess.call with shell=True
**Vulnerability:** Command injection vulnerability in `libs/utility_manager.py` where `subprocess.call(['start', filename], shell=True)` was used to open files on Windows.
**Learning:** Because Windows filenames can legally contain shell metacharacters like `&` and `^`, an `os.path.isfile()` check is insufficient to prevent command injection if `shell=True` is used.
**Prevention:** Always prefer using `os.startfile(filename)` over `subprocess.call(['start', filename], shell=True)` when launching or opening files on Windows.
