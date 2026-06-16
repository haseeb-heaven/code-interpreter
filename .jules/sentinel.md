## 2024-06-16 - Prevent Command Injection via `os.startfile`
**Vulnerability:** Command injection via user-controlled filenames passed to `subprocess.call(['start', filename], shell=True)`.
**Learning:** Using `shell=True` in Python's `subprocess` module is dangerous with arbitrary filenames, even if checked with `os.path.isfile()`. Windows shell interprets characters like `&` in names.
**Prevention:** Use `os.startfile(filename)` on Windows to open files without invoking a shell, ensuring safety and bypassing shell injection vectors.
