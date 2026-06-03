
## 2024-06-03 - Avoid shell=True for File Execution on Windows
**Vulnerability:** Command injection vulnerability via `subprocess.call` with `shell=True` when opening files on Windows.
**Learning:** Using `shell=True` with a list of arguments (like `['start', filename]`) exposes the application to command injection if the `filename` contains shell metacharacters (e.g., `&`, `;`).
**Prevention:** Use `os.startfile(filename)` to securely open files natively on Windows without invoking the shell.
