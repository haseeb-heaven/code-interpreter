## 2026-06-01 - Prevent Command Injection on Windows File Open
**Vulnerability:** Command injection vulnerability due to using `subprocess.call(['start', filename], shell=True)` on Windows in `UtilityManager._open_resource_file`.
**Learning:** Using `shell=True` with unvalidated input (like filenames) exposes the application to command injection.
**Prevention:** Use `os.startfile(filename)` instead to open files on Windows, which directly opens the file without invoking the command shell, avoiding the risk entirely.
