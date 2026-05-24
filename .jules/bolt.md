## 2024-05-24 - Pre-compiling Regex in Class Bodies
**Learning:** In Python 3, list comprehensions within a class body lack access to class scope, causing NameError when trying to pre-compile regexes. Also, pre-compiling regex arrays via `tuple(re.compile(p) for p in _PATTERNS)` yields a ~2x speedup in safety-critical loops.
**Action:** Use a generator expression converted to a tuple when pre-compiling patterns as class attributes, instead of relying on runtime `re.search()`.
