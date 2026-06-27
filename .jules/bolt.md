## 2024-06-27 - Pre-compiling Regex in safety-critical code
**Learning:** Re-compiling regular expressions repeatedly inside tight loops like `any()` in `assess_execution` adds significant overhead, even with Python's internal cache. Creating pre-compiled class-level tuple attributes of `re.Pattern` objects (`tuple(re.compile(p) for p in _PATTERNS)`) yields measurable performance improvements without sacrificing readability.
**Action:** Always pre-compile sets of regular expressions as class attributes when they are evaluated in repeated paths.
