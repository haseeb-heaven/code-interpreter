## 2025-02-26 - Command Injection via shell=True on Windows
**Vulnerability:** Using `subprocess.call(['start', filename], shell=True)` to open files on Windows introduces a command injection risk if `filename` contains shell metacharacters.
**Learning:** `shell=True` on Windows evaluates the entire command string through `cmd.exe`, which has complex and dangerous quoting rules that can execute arbitrary commands injected into the filename.
**Prevention:** Always use `os.startfile(filename)` on Windows to launch files safely without invoking the shell.
