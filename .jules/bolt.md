## 2025-06-25 - Pre-compiling Regex in Class Scope
**Learning:** In Python 3, list comprehensions created inside a class body do not have access to the class's scope. To pre-compile regular expressions using existing class attributes within the class body, use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`). This avoids `NameError` while providing a reliable speedup for repeated regex matching in `any()`.
**Action:** Always use generator expressions converted to tuples when pre-compiling regexes from other class attributes at the class level.
