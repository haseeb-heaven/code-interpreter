# Interpreter 3.2.0 Latest

@haseeb-heaven haseeb-heaven released this Apr 7, 2026

**3.2.0**

---

## 🔥 Release highlights:

* Introduced **secure code sandboxing (enabled by default)** with `/sandbox` and `/unsafe` toggles.
* Strengthened execution safety with **subprocess isolation, watchdog fixes, and process-group termination**.
* Improved safe-mode detection by eliminating multiple false positives and blocking new unsafe patterns.
* Enhanced execution reliability with **increased SAFE mode timeout (300s)** for long-running tasks.
* Refined build and release pipeline with **robust error handling and cleaner scripts**.

---

## 📜 Changelog:

* v3.2.0 - Added sandbox mode (default ON) with `/sandbox` and `/unsafe` toggles, improved subprocess security delegation, increased SAFE timeout to 300s, fixed watchdog timer issues, strengthened safe-mode pattern detection (write bypasses, absolute path escapes, destructive commands), added process-group kill on timeout, improved Python detection via `ast.parse`, cleaned execution flow formatting, and enhanced build_release.sh with robust helpers and error handling.
* v3.1.x - Fixed syntax errors in safety patterns, resolved test failures, added missing config files, improved unsafe mode handling via `safety_manager`, and applied CodeRabbit auto-fixes and unit tests.
* v3.0.0 - Introduced execution sandbox, circuit breaker, bounded repair retries, and improved CLI/TUI runtime output.

---

## 📦 Assets:

* interpreter.zip
* Source code (zip)
* Source code (tar.gz)

---

