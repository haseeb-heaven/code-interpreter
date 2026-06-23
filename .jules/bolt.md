## 2025-03-02 - Pre-compiling Regex in List Comprehensions
**Learning:** In Python 3, list comprehensions created inside a class body do not have access to the class's scope. Attempting to pre-compile regular expressions using existing class attributes within the class body via a list comprehension results in a `NameError`.
**Action:** To pre-compile regular expressions using existing class attributes within the class body, use a generator expression converted to a tuple (e.g., `tuple(re.compile(p, re.IGNORECASE) for p in _PATTERNS)`) instead of a list comprehension.
