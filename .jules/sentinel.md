## 2025-03-03 - Command Injection in UtilityManager._open_resource_file via `os.system` / `subprocess.call` shell=True
**Vulnerability:** The `UtilityManager._open_resource_file` method accepts a `filename` and opens it. On Windows, it uses `subprocess.call(['start', filename], shell=True)`. Filenames containing metacharacters (e.g. `&`) could lead to command injection even if `os.path.isfile(filename)` is true on Windows.
**Learning:** `os.path.isfile()` checks are insufficient to prevent command injection when `shell=True` is used on Windows, as valid Windows filenames can contain characters like `&` or `^`.
**Prevention:** Use `os.startfile(filename)` instead of `subprocess.call(['start', filename], shell=True)` on Windows to avoid opening a shell and preventing injection.
