## 2024-06-04 - Pre-compiling Regexes in Class Scope
**Learning:** In Python 3, list comprehensions created inside a class body do not have access to the class's scope. To pre-compile regular expressions using existing class attributes within the class body, use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) instead of a list comprehension to avoid `NameError`.
**Action:** Always use generator expressions converted to tuples when pre-compiling regex patterns as class-level attributes.
