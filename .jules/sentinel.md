## 2024-06-28 - Command Injection in Windows File Launch
**Vulnerability:** Command injection vulnerability via `subprocess.call(['start', filename], shell=True)` in `libs/utility_manager.py`.
**Learning:** On Windows, filenames can legally contain shell metacharacters like `&` and `^`. An `os.path.isfile()` check is insufficient to prevent command injection if `shell=True` is used.
**Prevention:** Always prefer `os.startfile(filename)` over `subprocess.call` with `shell=True` when launching or opening files on Windows.
