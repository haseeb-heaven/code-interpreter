import timeit
from libs.safety_manager import ExecutionSafetyManager

sm = ExecutionSafetyManager()
code = """
import os
import shutil
def test_func():
    pass
open('C:\\\\file', 'w').write('data')
"""

def bench():
    sm.assess_execution(code, "script")

n = 10000
duration = timeit.timeit(bench, number=n)
print(f"Before optimization: {duration:.4f} seconds for {n} iterations")
