## 2025-05-18 - Pre-compiling regex patterns in Python classes
**Learning:** Pre-compiling regexes as class-level attributes significantly reduces overhead in tight loops. However, in Python 3, list comprehensions inside a class body don't have access to the class scope, causing `NameError` when trying to use other class variables.
**Action:** Use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) instead of a list comprehension to initialize compiled regexes as class attributes.
