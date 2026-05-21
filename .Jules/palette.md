## 2025-02-27 - Strict vs Custom Case-Insensitivity with Rich Prompt Options
**Learning:** Using the `choices` parameter in `rich`'s `Prompt.ask()` automatically enforces strict, case-sensitive matching, which can break custom fallback case-insensitivity loops (especially impacting piped inputs).
**Action:** When working with `rich` prompts where case-insensitivity is expected but custom logic handles it, manually format the choices into the prompt text string (e.g. `[{'/'.join(options)}]`) instead of relying on the built-in `choices` parameter.
