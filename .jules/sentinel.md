## 2024-06-25 - Prevent Windows Command Injection in Resource Opener
**Vulnerability:** Command injection via `subprocess.call(['start', filename], shell=True)` on Windows when filename contains shell metacharacters (e.g., `&`). `os.path.isfile()` check does not prevent this because filenames can legally contain these characters.
**Learning:** Using `shell=True` to open files on Windows is inherently unsafe with untrusted or complex filenames, even if the file exists.
**Prevention:** Prefer `os.startfile(filename)` on Windows to safely launch files using their associated applications without invoking the shell.
