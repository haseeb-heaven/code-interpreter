## 2024-05-24 - Optimizing Safety Manager Regex Compilation
**Learning:** Pre-compiling `re.Pattern` objects inside a list comprehension causes a `NameError` in class bodies under Python 3, so a generator cast to a `tuple` should be used instead. By bypassing `re.search`'s cache lookup, a significant speedup in repeated loop executions was achieved for evaluating safety checks.
**Action:** Pre-compile regular expressions as a tuple at the class level for any methods that perform multiple evaluations within `any()` loops.
