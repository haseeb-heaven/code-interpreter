## 2024-05-18 - Path Traversal in File Name Resolution
**Vulnerability:** The `UtilityManager.get_full_file_path` method was vulnerable to Path Traversal because it combined `os.getcwd()` with the input file name using `os.path.join` without ensuring the final path stayed within the current working directory, allowing paths like `../etc/passwd` or `/etc/passwd`.
**Learning:** Naively checking `not os.path.isabs(file_name)` and appending to `os.getcwd()` does not protect against relative path traversal attacks or directory escapes.
**Prevention:** Always convert user-provided file paths to absolute paths using `os.path.abspath`, and use a strict boundary check like `os.path.commonpath([cwd, full_path]) == cwd` to ensure the resolved path does not escape the intended root directory.
