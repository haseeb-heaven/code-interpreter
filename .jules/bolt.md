## 2024-05-18 - Pre-compiled Regexes in Safety Manager
**Learning:** While Python caches up to 512 regex strings, explicitly using pre-compiled `re.Pattern` objects (`p.search(text)`) in list comprehensions with `any()` yields measurable speedup in tight validation loops. Furthermore, extracting statically defined lists to class-level properties prevents them from being re-allocated upon each function call.
**Action:** Extract list allocations inside functions into class properties, and pre-compile any regex strings used inside loops or list comprehensions directly in the class definition.
