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

def bench_old():
    sm.assess_execution(code, "script")

n = 10000
duration_old = timeit.timeit(bench_old, number=n)

print(f"Old: {duration_old:.4f}")
