## 2025-05-15 - [Pre-compile Regex Patterns in Safety Manager]
**Learning:** While Python's `re` module caches up to 512 regexes, bypassing this lookup cache by directly executing pre-compiled `re.Pattern` objects (`p.search(text)`) provides a measurable performance improvement in tight, safety-critical evaluation loops.
**Action:** Always pre-compile regexes as class-level tuple attributes in hot paths where pattern matching is repeatedly performed.
