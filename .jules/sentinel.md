## 2026-05-25 - Prevent Command Injection in Windows File Opening
**Vulnerability:** Command injection vulnerability via `subprocess.call(['start', filename], shell=True)`.
**Learning:** Using `shell=True` with unvalidated input on Windows can lead to command injection. `os.startfile()` is safer for opening files with associated applications on Windows.
**Prevention:** Prefer `os.startfile(filename)` over `subprocess.call` with `shell=True` for opening files on Windows.
