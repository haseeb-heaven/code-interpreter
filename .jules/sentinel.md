## 2025-01-01 - Command Injection via `shell=True` on Windows File Execution
**Vulnerability:** Command injection when opening files on Windows using `subprocess.call(['start', filename], shell=True)`.
**Learning:** `os.path.isfile(filename)` is insufficient to prevent command injection because valid Windows filenames can contain shell metacharacters like `&` and `^`.
**Prevention:** Use `os.startfile(filename)` which executes the file with its associated application without involving a shell.