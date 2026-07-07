## 2024-07-07 - Pre-compiled Regex Patterns in tight loops
**Learning:** Bypassing `re` module's internal cache lookup by executing pre-compiled `re.Pattern` objects in tight loops yields measurable performance improvements.
**Action:** Always pre-compile frequently used regex patterns into `re.Pattern` objects as class-level attributes, using generator expressions converted to tuples to avoid class body scope issues.
