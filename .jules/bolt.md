## 2024-05-24 - Pre-compile regular expressions in safety-critical loops
**Learning:** Using `re.search` with string patterns in tight loops (like those in `ExecutionSafetyManager`) introduces unnecessary overhead. Bypassing the cache by executing pre-compiled `re.Pattern` objects (`p.search(text)`) is measurably faster.
**Action:** Always pre-compile regular expressions as class-level attributes using generator expressions converted to tuples (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) when optimizing repeated regex matching with `any()` inside class methods.
