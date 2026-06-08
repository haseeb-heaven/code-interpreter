## 2024-06-08 - OS Command Injection in Windows Resource Opener
**Vulnerability:** Command injection vulnerability via `subprocess.call(['start', filename], shell=True)` when handling file paths in Windows.
**Learning:** Using `shell=True` with user-supplied or external inputs (even file paths) can lead to arbitrary command execution on Windows.
**Prevention:** Use `os.startfile(filename)` instead of shelling out on Windows, which directly leverages the OS API without a command shell layer.
