## 2024-05-18 - Pre-compile Regex Patterns
**Learning:** Pre-compiling lists of regex patterns into class attributes prevents redundant compilation inside hot loops (like code safety checking in `assess_execution`). Python 3 requires generator expressions instead of list comprehensions when doing this at the class level due to scope resolution for class variables.
**Action:** Always use pre-compiled regex objects stored as tuples (e.g., `tuple(re.compile(p) for p in PATTERNS)`) for frequently evaluated lists of patterns to minimize overhead.
