
## 2024-05-24 - Windows Shell Invocation Vulnerability
**Vulnerability:** Invoking shell=True with subprocess on Windows to open files (e.g., `subprocess.call(['start', filename], shell=True)`) creates a command injection risk if `filename` contains unvalidated input.
**Learning:** Windows platforms offer native `os.startfile()` which is immune to this specific shell injection attack vector.
**Prevention:** Always prefer `os.startfile(filename)` over `subprocess.call(..., shell=True)` for opening files on Windows.
