## 2025-03-05 - Pre-compiling Regexes in Class Scope
**Learning:** In Python 3, list comprehensions inside a class body do not have access to the class's scope, leading to `NameError` if trying to pre-compile existing class attribute lists of regexes.
**Action:** Use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) to successfully pre-compile regexes at the class level to avoid performance overhead in safety-critical paths.
