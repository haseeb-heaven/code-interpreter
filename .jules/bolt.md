## 2025-07-05 - Pre-compile Regex Patterns in Safety Manager
**Learning:** In highly-frequent code paths (like AST walking or safety checks on every code string), calling `re.search` with a raw string pattern inside an `any()` generator can be significantly slower than pre-compiling the regex and calling `p.search`.
**Action:** Always pre-compile regular expressions as class-level attributes when they are evaluated in loops or high-frequency paths.
