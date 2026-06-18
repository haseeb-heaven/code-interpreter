## 2024-06-18 - Prevent Command Injection via os.startfile on Windows
**Vulnerability:** Command injection vulnerability via `subprocess.call(['start', filename], shell=True)` in `_open_resource_file`.
**Learning:** Windows filenames can legally contain shell metacharacters like `&` and `^`. An `os.path.isfile()` check is insufficient to prevent command injection if `shell=True` is used.
**Prevention:** Prefer using `os.startfile(filename)` over `subprocess.call` with `shell=True` when opening files natively on Windows.
