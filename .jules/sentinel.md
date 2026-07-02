## 2024-07-02 - Command Injection in Windows File Open
**Vulnerability:** Command injection vulnerability due to `subprocess.call(['start', filename], shell=True)` when opening files on Windows.
**Learning:** Valid Windows file paths can legally contain shell metacharacters like `&` and `^`. A simple `os.path.isfile` check does not prevent these characters from being evaluated by the shell when `shell=True` is used.
**Prevention:** Use `os.startfile(filename)` instead of `subprocess.call` with `shell=True` when opening files on Windows to safely avoid shell metacharacter injection.
