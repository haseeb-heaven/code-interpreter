## 2025-05-24 - Pre-compile regular expressions
**Learning:** Pre-compiling regular expressions in Python avoids repetitive compilation overhead in safety-critical code execution paths.
**Action:** Extract list of regex patterns and literal patterns into class-level variables initialized using `re.compile`. Then use `p.search` or `p.findall` in repeated iterations, such as evaluating code blocks against destructive patterns.
