# Interpreter 3.2.3 Latest

@haseeb-heaven haseeb-heaven released this Jul 11, 2026

**3.2.3**

---

## 🔥 Release highlights:

* Resolved **Command Injection vulnerability** in file opening by replacing `subprocess.call` with `os.startfile` on Windows.
* Mitigated **Path Traversal vulnerability** in `UtilityManager.get_full_file_path` with strict boundary checks.
* Enhanced stability with **timeouts on all external HTTP requests** to prevent application hanging.
* Boosted performance by **pre-compiling all regex patterns** in `ExecutionSafetyManager`.
* Improved **Terminal UI accessibility**, ensuring prompt choices fallbacks are explicitly visible in non-TTY environments.
* Fixed **Ollama "NoneType" Error**, allowing robust extraction of direct string responses and dictionary outputs for local models like Mistral.
* Fixed **Ollama API Key Error**, intentionally bypassing `HUGGINGFACE_API_KEY` requirements for local and Ollama models.
* Updated **legacy model configurations** to point to the modern 2026 stable aliases (e.g. `gpt-4.1`, `claude-sonnet-4-6`).
* **Expanded unit test coverage to 263 tests**, directly validating security fixes, UX enhancements, and API Key robustness logic.

---

## 📜 Changelog:
* v3.2.3 - Fixed Windows command injection, resolved path traversal in utility manager, implemented HTTP timeouts, optimized SafetyManager by pre-compiling regexes, improved non-TTY fallback prompts, fixed Ollama/local model API Key extraction and output parsing, updated legacy model configurations, and expanded test suite with full coverage.
* v3.2.2 - Added sandbox mode (default ON) with */sandbox* and */unsafe* toggles, replaced *--unsafe* with **--sandbox / --no-sandbox**, improved subprocess security delegation, increased SAFE timeout to 300s, fixed watchdog timer issues, strengthened safe-mode protection, added process-group kill on timeout, improved Python detection using AST parsing, fixed multiple security vulnerabilities (P0/P1/P2).

---

## 📦 Assets:

* interpreter.zip
* Source code (zip)
* Source code (tar.gz)

---
