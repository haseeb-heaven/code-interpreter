## 2024-05-12 - Command Injection in Resource Opener
**Vulnerability:** Command injection on Windows via `subprocess.call(['start', filename], shell=True)` in `UtilityManager._open_resource_file`.
**Learning:** Using `shell=True` on Windows with user-supplied input (like a filename) is dangerous. Even though it was intended to simply open a file, passing a malicious filename could execute arbitrary system commands.
**Prevention:** Use `os.startfile(filename)` on Windows to natively and securely open files without invoking a shell.
