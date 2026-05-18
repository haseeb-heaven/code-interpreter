## 2025-05-18 - Avoid cache eviction regressions
**Learning:** Pre-compiling regex lists by moving a list comprehension into a `tuple(...)` *inside* a method's execution path causes performance regressions by creating a new compiled tuple every time the function is called. The original code implicitely benefited from `re` internal cache which was faster.
**Action:** When migrating pattern arrays to explicit `re.compile`, ensure they are elevated to *class-level* attributes and not evaluated repeatedly at runtime inside instance methods.
