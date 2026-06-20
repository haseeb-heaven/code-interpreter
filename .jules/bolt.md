## 2024-05-24 - Pre-compiling Regexes for any() Loops
**Learning:** While Python's `re` module internally caches up to 512 compiled regex patterns, bypassing this cache lookup by directly executing pre-compiled `re.Pattern` objects (e.g., `p.search(text)`) yields measurable performance improvements in tight loops, specifically inside `any()` comprehensions over multiple patterns.
**Action:** Pre-compile individual patterns into a tuple of `re.Pattern` objects when iterating in `any()` loops, rather than calling `re.search` repeatedly with string patterns.
