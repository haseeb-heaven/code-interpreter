## 2025-02-24 - Pre-compile regex for performance
**Learning:** Re-compiling regexes in tight loops with `any()` is slow in Python.
**Action:** Use `tuple(re.compile(p) for p in _PATTERNS)` at the class level instead.
