import timeit
import re

class OldManager:
    _WRITE_PATTERNS = [
        r'open\s*\([^)]*[\'"]w[btax]?\+?[\'"]',
        r'open\s*\([^)]*[\'"]a[btx]?\+?[\'"]',
        r'open\s*\([^)]*[\'"]x[bt]?\+?[\'"]',
        r'open\s*\([^)]*[\'"]r[bt]?\+[\'"]',
        r'open\s*\([^)]*mode\s*=\s*[\'"]w[btax]?\+?',
        r'open\s*\([^)]*mode\s*=\s*[\'"]a[btx]?\+?',
        r'open\s*\([^)]*mode\s*=\s*[\'"]x[bt]?\+?',
        r'open\s*\([^)]*mode\s*=\s*[\'"]r[bt]?\+',
        r"\.write_text\s*\(",
        r"\.write_bytes\s*\(",
        r"\bwriteFile\s*\(",
        r"\bwriteFileSync\s*\(",
        r"\bappendFile\s*\(",
        r"\bappendFileSync\s*\(",
        r'\.to_csv\s*\([^)]*[\'"/]',
        r'\.to_json\s*\([^)]*[\'"/]',
        r'\.to_html\s*\([^)]*[\'"/]',
        r'\.to_excel\s*\([^)]*[\'"/]',
        r'\.to_parquet\s*\([^)]*[\'"/]',
    ]

    def _has_write_operation(self, code: str) -> bool:
        return any(re.search(p, code, re.IGNORECASE) for p in self._WRITE_PATTERNS)

class NewManager:
    _WRITE_PATTERNS = OldManager._WRITE_PATTERNS
    _COMPILED_WRITE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _WRITE_PATTERNS)

    def _has_write_operation(self, code: str) -> bool:
        return any(p.search(code) for p in self._COMPILED_WRITE_PATTERNS)

old_m = OldManager()
new_m = NewManager()

code = """
def test_func():
    pass
# some more code here
# to make the regex search realistic
"""

n = 100000

t_old = timeit.timeit(lambda: old_m._has_write_operation(code), number=n)
t_new = timeit.timeit(lambda: new_m._has_write_operation(code), number=n)

print(f"Old: {t_old:.4f}")
print(f"New: {t_new:.4f}")
print(f"Improvement: {(t_old - t_new) / t_old * 100:.2f}%")
