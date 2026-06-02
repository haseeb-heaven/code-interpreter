
## 2025-01-01 - Avoid shell=True for Opening Files
**Vulnerability:** Use of `subprocess.call(['start', filename], shell=True)` for opening resource files on Windows.
**Learning:** Using `shell=True` can expose the application to command injection vulnerabilities if `filename` contains unsanitized input.
**Prevention:** Use `os.startfile(filename)` on Windows, which natively opens the file without invoking a shell.
