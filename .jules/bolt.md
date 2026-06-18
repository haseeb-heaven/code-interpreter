## 2024-05-18 - Pre-compile Regex Patterns for Performance
**Learning:** When using `any()` with list comprehensions for regex matching in tight or safety-critical loops, pre-compiling individual patterns into a tuple of `re.Pattern` objects provides measurable speedups over repeated `re.search` calls.
**Action:** Statically compile repeated regex patterns at the class level via `tuple(re.compile(p) for p in (...))` instead of a list of strings, to bypass internal cache lookups and reduce evaluation overhead.
