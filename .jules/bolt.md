## 2024-06-29 - Pre-compiling Regex in Tight Loops
**Learning:** While Python's `re` module caches up to 512 regex strings, directly calling `.search()` on pre-compiled `re.Pattern` objects provides a measurable speedup (~2x) in tight loops like safety validators checking large sets of patterns.
**Action:** Always pre-compile regex lists to `re.Pattern` objects using tuple generator expressions (to avoid scope issues inside class bodies) when optimizing repeated regex matching loops.
