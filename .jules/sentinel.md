## 2024-05-31 - Safe File Opening on Windows
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` when opening files on Windows.
**Learning:** Using `shell=True` with list arguments can still lead to command injection on Windows because the shell evaluates metacharacters.
**Prevention:** Use `os.startfile(filename)` on Windows, which natively handles file opening without invoking the command shell.
