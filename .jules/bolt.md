
## 2024-05-18 - Pre-compiling regex lists in class body
**Learning:** When optimizing repeated regex matching in list comprehensions with `any()`, pre-compiling individual patterns into a tuple of `re.Pattern` objects provides a reliable speedup. In Python 3, list comprehensions created inside a class body do not have access to the class's scope. A generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) must be used instead of a list comprehension to avoid `NameError`.
**Action:** Always use generator expressions converted to tuples when pre-compiling regexes based on other class attributes directly within a class body definition.
