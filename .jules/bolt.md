## 2024-05-24 - Pre-compiling Regexes inside Python Class Bodies
**Learning:** Re-compiling regexes internally inside tight loops like safety checks degrades performance, caching them directly bypasses the `re` internal cache lookup. However, list comprehensions inside a class body don't have access to class scope variables, causing a NameError.
**Action:** Use a generator expression converted to a tuple (e.g., `tuple(re.compile(p) for p in _PATTERNS)`) instead of list comprehensions when pre-compiling regexes as class attributes.
