import timeit
from libs.safety_manager import ExecutionSafetyManager
import re

sm = ExecutionSafetyManager()

code = """
import os
import shutil

def test_func():
    pass
open('C:\\\\file', 'w').write('data')
"""

def bench_new():
    sm.assess_execution(code, "script")

n = 10000
duration_new = timeit.timeit(bench_new, number=n)

print(f"New: {duration_new:.4f}")
