## 2024-06-04 - Command Injection via subprocess.call with shell=True on Windows
**Vulnerability:** Invoking `subprocess.call(['start', filename], shell=True)` on Windows to open files allows command injection if `filename` contains shell metacharacters.
**Learning:** Using `shell=True` with unsanitized input is dangerous, especially on Windows where `start` is a shell builtin. The codebase was using this to open resource files in `libs/utility_manager.py`.
**Prevention:** Prefer `os.startfile(filename)` on Windows instead of `subprocess.call` with `shell=True` to safely open files without shell interpolation risks.
