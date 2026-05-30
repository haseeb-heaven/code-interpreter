## 2024-05-30 - Command Injection in Windows File Opening
**Vulnerability:** `subprocess.call(['start', filename], shell=True)` was used to open files on Windows, allowing potential command injection if the filename is maliciously crafted.
**Learning:** Using `shell=True` with user-supplied arguments is dangerous. On Windows, `os.startfile()` is a safer and standard alternative for opening files with their associated applications.
**Prevention:** Avoid `shell=True` when executing commands with variable inputs, and prefer built-in OS functions like `os.startfile()` for file operations on Windows.
