## 2024-06-20 - Fix Command Injection in Windows File Opening
**Vulnerability:** Command injection risk due to `subprocess.call(['start', filename], shell=True)` when opening files on Windows.
**Learning:** `os.path.isfile()` check does not prevent command injection on Windows because legal filenames can contain shell metacharacters like `&` and `^`.
**Prevention:** Prefer `os.startfile(filename)` to open files on Windows instead of relying on shell execution.
