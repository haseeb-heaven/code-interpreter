## 2025-03-05 - Command Injection in Resource File Opener
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` on Windows in `libs/utility_manager.py`.
**Learning:** Using `shell=True` with unvalidated input (like filenames) can allow arbitrary command execution if the input contains shell metacharacters.
**Prevention:** Use `os.startfile(filename)` on Windows to open files securely without invoking a shell.
