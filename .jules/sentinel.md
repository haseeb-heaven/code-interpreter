## 2024-05-20 - Command Injection via Windows shell=True
**Vulnerability:** Invoking `subprocess.call(['start', filename], shell=True)` on Windows to open a file introduces a command injection vulnerability if the filename contains shell metacharacters.
**Learning:** `shell=True` parses the string in the command shell, allowing trailing command execution. Using lists with `shell=True` on Windows does not escape arguments.
**Prevention:** Always use `os.startfile(filename)` on Windows to open documents or applications to avoid the shell entirely.