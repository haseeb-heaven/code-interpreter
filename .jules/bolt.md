## 2024-05-24 - Pre-compiling Regexes in Class Scope
**Learning:** In Python 3, list comprehensions in a class body cannot access the class's scope. Attempting `[re.compile(p) for p in _PATTERNS]` causes a `NameError`.
**Action:** Use a generator expression converted to a tuple `tuple(re.compile(p) for p in _PATTERNS)` when pre-compiling regexes as class-level attributes.
