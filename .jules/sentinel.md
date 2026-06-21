## 2024-05-24 - Command Injection via shell=True
**Vulnerability:** Command injection vulnerability in `UtilityManager._open_resource_file` when opening files on Windows.
**Learning:** Checking `os.path.isfile(filename)` is not sufficient to prevent command injection because Windows filenames can legally contain shell metacharacters like `&` and `^`.
**Prevention:** Use `os.startfile(filename)` instead of `subprocess.call` with `shell=True` to safely open files on Windows.