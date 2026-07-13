## 2024-07-08 - Pre-compile Regex with Tuple Generator in Class Body
**Learning:** In Python 3, list comprehensions in a class body do not have access to the class's scope, leading to `NameError` if referencing a class variable directly.
**Action:** Use a generator expression converted to a tuple (`tuple(re.compile(p) for p in _PATTERNS)`) for pre-compiling regex lists at the class level to bypass the cache and gain a measurable (~10-15%) performance speedup without scoping errors.
## 2024-10-24 - AST parsing overhead in validation pipelines
**Learning:** `ast.parse` is significantly heavier than pre-compiled regex searches, introducing unnecessary performance overhead when placed before fast regex checks in validation pipelines like `libs/safety_manager.py`.
**Action:** Structure early-return validation checks to execute fast regex pattern searches before heavier operations like AST parsing.
