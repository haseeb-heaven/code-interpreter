## 2024-05-23 - Command Injection in Resource Opener
**Vulnerability:** Command injection via shell metacharacters in valid Windows filenames when using `subprocess.call(['start', filename], shell=True)`.
**Learning:** An `os.path.isfile()` check is insufficient to prevent command injection because Windows filenames can legally contain characters like `&` and `^`.
**Prevention:** Use `os.startfile(filename)` which bypasses the shell entirely, safely opening the file without command injection risk.