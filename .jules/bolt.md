## 2024-06-21 - Pre-compiling regexes for tight loops
**Learning:** Bypassing `re` module cache lookup by directly executing pre-compiled `re.Pattern` objects (`p.search(text)`) instead of `re.search(p, text)` yields measurable performance improvements in safety-critical tight loops, particularly inside `any()` comprehensions.
**Action:** Use `tuple(re.compile(p, re.IGNORECASE) for p in _PATTERNS)` inside class definitions to compile regex sets ahead of time, ensuring optimal performance for security and safety assessments.
