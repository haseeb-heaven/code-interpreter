## 2025-03-05 - Windows Command Injection via subprocess.call
**Vulnerability:** Command Injection vulnerability exists when using `subprocess.call(['start', filename], shell=True)` because `shell=True` on Windows allows attackers to execute arbitrary shell commands if the filename contains shell metacharacters (e.g. `&` or `^`), even if it passes `os.path.isfile()`.
**Learning:** Checking if a file exists (`os.path.isfile()`) is insufficient to prevent command injection on Windows when `shell=True` is used, because legal Windows filenames can contain metacharacters that the shell interprets.
**Prevention:** Always prefer `os.startfile(filename)` over `subprocess.call` with `shell=True` for opening files on Windows.
