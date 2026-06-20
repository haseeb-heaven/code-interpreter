import time
import re

patterns = [r"foo", r"bar", r"baz", r"qux", r"quux", r"corge", r"grault", r"garply", r"waldo", r"fred", r"plugh", r"xyzzy", r"thud"]

start = time.time()
for _ in range(10000):
    any(re.search(p, "test text") for p in patterns)
print(f"Original: {time.time() - start:.4f}s")

compiled = tuple(re.compile(p) for p in patterns)

start = time.time()
for _ in range(10000):
    any(p.search("test text") for p in compiled)
print(f"Pre-compiled: {time.time() - start:.4f}s")
