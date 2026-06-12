## 2026-06-12 - Prevent Command Injection on Windows File Open
**Vulnerability:** Invoking `subprocess.call` with `shell=True` and a user-supplied filename to open a file on Windows introduces a command injection risk.
**Learning:** Even when `subprocess.call` is passed a list of arguments, setting `shell=True` on Windows can execute arbitrary shell commands if the filename contains shell metacharacters.
**Prevention:** Use `os.startfile(filename)` on Windows, which natively opens files with their associated applications without invoking a shell.
