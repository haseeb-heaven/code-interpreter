import re

class Test:
    _WRITE_PATTERNS = [r'a', r'b']

    def method_one(self):
        pass

    _COMPILED_WRITE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _WRITE_PATTERNS)

print(Test._COMPILED_WRITE_PATTERNS)
