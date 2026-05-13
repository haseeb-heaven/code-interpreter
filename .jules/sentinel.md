## 2025-05-13 - Path Traversal in File Context Extraction
**Vulnerability:** Path traversal in `libs/utility_manager.py`'s `get_full_file_path` allowed attackers to include arbitrary files (e.g., `../../etc/passwd`) by manipulating the prompt input used for context extraction. The file paths weren't correctly validated to be within the application's working directory.
**Learning:** `os.path.join(os.getcwd(), path)` is unsafe when `path` contains `../`. Python's `os.path.join` does not normalize paths, and using `open` on the resulting string will traverse outside the base path.
**Prevention:** Always use `os.path.abspath(os.path.join(cwd, file_name))` and assert that `full_path.startswith(os.path.abspath(cwd))` before operating on the path.
