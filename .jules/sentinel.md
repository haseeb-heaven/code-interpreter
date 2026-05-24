## 2026-05-24 - Avoid shell=True on Windows for file opening
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` on Windows.
**Learning:** Invoking the shell to open files directly exposes the application to command injection if `filename` is unescaped.
**Prevention:** Prefer `os.startfile(filename)` over `subprocess.call` with `shell=True` for opening files on Windows.
