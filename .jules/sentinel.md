## 2024-05-24 - [Command Injection Risk in File Launcher]
**Vulnerability:** Potential command injection vulnerability when launching files on Windows using `subprocess.call` with `shell=True`.
**Learning:** Using `shell=True` with dynamic variables (like `filename`) exposes the application to command injection because the shell interprets metacharacters. `start` is a shell internal command requiring `shell=True`, compounding the risk.
**Prevention:** Use `os.startfile()` on Windows to securely open files natively without relying on shell interpretation.
