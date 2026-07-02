## 2024-05-18 - Optimize execution safety checks
**Learning:** AST parsing is a heavy operation compared to regex matching. In security pipelines, running expensive checks before fast checks can cause severe performance penalties on blocked operations.
**Action:** Always place fast regex and string matching blocks before `ast.parse` in validation pipelines to allow early-return failures.
