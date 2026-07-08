## 2024-07-08 - Fix command injection vulnerability in file opening
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` on Windows in `libs/utility_manager.py`.
**Learning:** `os.path.isfile(filename)` is insufficient to prevent command injection when using `shell=True` on Windows because valid filenames can contain shell metacharacters like `&` and `^`.
**Prevention:** Avoid `shell=True` and prefer direct API hooks like `os.startfile(filename)` for opening files securely on Windows.
