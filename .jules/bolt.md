## 2026-05-28 - Regex precompilation inside Python class bodies
**Learning:** Pre-compiling lists of regular expressions inside a Python class body using list comprehensions raises a `NameError` because class scope variables are not available within the comprehension scope.
**Action:** Use a generator expression combined with a `tuple()` conversion, for example: `_COMPILED_PATTERNS = tuple(re.compile(p) for p in _PATTERNS)` to pre-compile the list as class variables safely.
