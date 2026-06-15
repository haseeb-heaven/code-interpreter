## 2025-06-15 - Command Injection in Resource Opening
**Vulnerability:** Command injection vulnerability when opening resource files on Windows.
**Learning:** Using `subprocess.call(['start', filename], shell=True)` is dangerous even if `os.path.isfile(filename)` is checked, as Windows allows shell metacharacters like `&` in filenames.
**Prevention:** Use `os.startfile(filename)` for opening files safely on Windows, which directly calls the ShellExecute API and avoids the shell command interpreter.
