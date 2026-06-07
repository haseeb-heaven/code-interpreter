## 2025-02-23 - Command Injection in Windows File Launch
**Vulnerability:** Using `subprocess.call(['start', filename], shell=True)` for opening files on Windows creates a command injection risk if `filename` contains shell metacharacters.
**Learning:** Passing a list to `subprocess.call` with `shell=True` does not safely quote arguments on Windows, allowing execution of arbitrary commands if the file path is malicious.
**Prevention:** Use `os.startfile(filename)` on Windows to open files securely without invoking the command shell.
