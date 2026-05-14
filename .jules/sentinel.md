## 2024-05-14 - Path Traversal in File Resolution
**Vulnerability:** Path traversal in `utility_manager.py`'s `get_full_file_path` method. Using `os.path.join(cwd, file_name)` without validating the resulting path allowed directory traversal (e.g., `../etc/passwd`).
**Learning:** `os.path.join` does not normalize paths or verify they stay within a base directory, which is a common pitfall when handling user-provided file names.
**Prevention:** Always normalize the concatenated path with `os.path.abspath()` and verify it is within the expected base directory using `os.path.commonpath([cwd, full_path]) == cwd`. Do not use `.startswith(cwd)` as it can allow sibling directory traversal (e.g., `/base` matching `/base-secrets`).
