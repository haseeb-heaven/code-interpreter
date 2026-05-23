import re

class TestManager:
    _WRITE_PATTERNS = [
        r'open\s*\([^)]*[\'"]w[btax]?\+?[\'"]',
    ]

    # test using generator expression converted to tuple
    _COMPILED_WRITE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _WRITE_PATTERNS)

    def _has_write_operation(self, code: str) -> bool:
        return any(p.search(code) for p in self._COMPILED_WRITE_PATTERNS)

t = TestManager()
print(t._has_write_operation("open('file', 'w')"))
