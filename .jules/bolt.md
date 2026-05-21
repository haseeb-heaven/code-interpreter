## 2025-05-21 - Pre-compile Regexes in Safety Manager
**Learning:** In Python 3, list comprehensions created inside a class body do not have access to the class's scope. To pre-compile regular expressions using existing class attributes within the class body, use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) instead of a list comprehension to avoid `NameError`.
**Action:** Always use generator expressions converted to tuples for pre-compiling class-level regexes based on other class attributes.
