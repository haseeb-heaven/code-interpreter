## 2024-05-30 - Class-level Tuple Regex Pre-compilation
**Learning:** Optimizing repeated regex matching in list comprehensions with `any()` by pre-compiling `re.Pattern` objects provides a reliable speedup. Extracting statically defined lists to class-level attributes avoids allocation overhead. Using generator expressions converted to tuples (e.g. `tuple(re.compile(p) for p in PATTERNS)`) avoids `NameError` in class bodies in Python 3.
**Action:** Always extract static pattern lists and use `tuple(re.compile(p))` to pre-compile regexes as class attributes for performance-critical loops.
