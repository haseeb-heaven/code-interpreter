## 2024-07-03 - Windows File Launch Command Injection
**Vulnerability:** `subprocess.call(['start', filename], shell=True)` was used to open files on Windows, creating a command injection risk even with `os.path.isfile()` checks, as legal filenames can contain shell metacharacters (`&`, `^`).
**Learning:** Using `shell=True` with `start` on user-controlled or external paths is inherently unsafe on Windows because the shell parses metacharacters before the application opens the file.
**Prevention:** Always use `os.startfile(filename)` for opening files natively on Windows, bypassing the shell entirely.
