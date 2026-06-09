## 2025-05-18 - Pre-compiled Regexes for Safety Checks
**Learning:** Using `re.search(p, text)` within `any()` on raw string lists causes repeated regex compilation overhead in tight safety-check loops.
**Action:** Pre-compile patterns into a tuple of `re.Pattern` objects using `tuple(re.compile(p) for p in ...)` as class attributes to significantly speed up assessment.
