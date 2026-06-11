## 2024-05-18 - Avoid subprocess with shell=True for OS file operations
**Vulnerability:** Command Injection via `subprocess.call` with `shell=True` when handling user-provided file paths.
**Learning:** Using `subprocess.call(["start", filename], shell=True)` on Windows makes the application highly vulnerable to shell injection if `filename` contains shell metacharacters (e.g., `&`, `|`, `;`).
**Prevention:** Always prefer using native, secure APIs like `os.startfile(filename)` on Windows, which directly dispatches the file to the OS shell handler without routing through `cmd.exe` or executing embedded commands.
