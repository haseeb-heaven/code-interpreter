"""Unit + integration tests for sandboxed execution & security hardening (#225)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.execution.docker_sandbox import is_docker_available, run_in_docker
from libs.execution.resource_monitor import measure
from libs.execution.sandbox_subprocess import run_in_subprocess
from libs.safety_manager import ExecutionSafetyManager, SafetyLevel
from libs.security.audit_log import clear_audit, format_recent, log_execution, read_recent
from libs.security.path_ignore import is_path_protected, load_ignore_patterns
from libs.security.secret_scanner import format_secret_warning, scan_code


class TestSubprocessSandbox(unittest.TestCase):
	def test_runs_python(self):
		result = run_in_subprocess('print("hi-225")', timeout=10, language="python")
		self.assertFalse(result["timed_out"])
		self.assertEqual(result["returncode"], 0)
		self.assertIn("hi-225", result["stdout"])

	def test_timeout(self):
		result = run_in_subprocess(
			"import time\ntime.sleep(5)",
			timeout=1,
			language="python",
		)
		self.assertTrue(result["timed_out"])
		self.assertIn("timed out", result["stderr"].lower())


class TestDockerSandbox(unittest.TestCase):
	def test_is_docker_available_bool(self):
		self.assertIsInstance(is_docker_available(), bool)

	def test_run_without_docker_returns_error(self):
		with patch("libs.execution.docker_sandbox.subprocess.run", side_effect=FileNotFoundError):
			result = run_in_docker("print(1)", timeout=5)
			self.assertNotEqual(result["returncode"], 0)
			self.assertIn("Docker", result["stderr"])


class TestSecretScanner(unittest.TestCase):
	def test_detects_openai_key(self):
		code = 'key = "sk-' + ("a" * 24) + '"'
		hits = scan_code(code)
		self.assertTrue(hits)
		self.assertEqual(hits[0].pattern_name, "OpenAI API Key")
		self.assertIn("****", hits[0].masked_value)
		self.assertNotIn("a" * 20, format_secret_warning(hits))

	def test_clean_code(self):
		self.assertEqual(scan_code("print(1+1)"), [])


class TestAuditLog(unittest.TestCase):
	def test_log_and_read(self):
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / "audit.jsonl"
			entry = log_execution(
				task="sum",
				code="print(1)",
				output="1",
				model="local-model",
				language="python",
				sandbox="subprocess",
				duration_ms=12,
				path=path,
			)
			self.assertIn("code_hash", entry)
			self.assertNotIn("print(1)", path.read_text(encoding="utf-8"))
			rows = read_recent(5, path=path)
			self.assertEqual(len(rows), 1)
			self.assertIn("sum", format_recent(5, path=path))
			self.assertTrue(clear_audit(path=path))
			self.assertFalse(path.exists())


class TestPathIgnore(unittest.TestCase):
	def test_load_and_match(self):
		with tempfile.TemporaryDirectory() as tmp:
			ignore = Path(tmp) / "ignore"
			ignore.write_text("~/.ssh/\n**/.env\n", encoding="utf-8")
			patterns = load_ignore_patterns(ignore)
			self.assertTrue(len(patterns) >= 2)
			ssh = str(Path.home() / ".ssh" / "id_rsa")
			self.assertTrue(is_path_protected(ssh, patterns))


class TestSafetyLevels(unittest.TestCase):
	def test_strict_blocks_network(self):
		sm = ExecutionSafetyManager(safety_level=SafetyLevel.STRICT)
		d = sm.assess_execution("import requests\nrequests.get('http://x')", mode="code")
		self.assertFalse(d.allowed)

	def test_strict_allows_pure_math(self):
		sm = ExecutionSafetyManager(safety_level="strict")
		d = sm.assess_execution("print(2+2)", mode="code")
		self.assertTrue(d.allowed)

	def test_relaxed_warns_but_allows(self):
		sm = ExecutionSafetyManager(safety_level=SafetyLevel.RELAXED)
		d = sm.assess_execution("import os; os.system('echo hi')", mode="code")
		self.assertTrue(d.allowed)
		self.assertTrue(d.reasons)

	def test_off_allows(self):
		sm = ExecutionSafetyManager(safety_level="off")
		self.assertTrue(sm.unsafe_mode)
		d = sm.assess_execution("shutil.rmtree('/')", mode="code")
		self.assertTrue(d.allowed)


class TestResourceMonitor(unittest.TestCase):
	def test_measure_duration(self):
		with measure() as usage:
			_ = sum(range(1000))
		self.assertGreaterEqual(usage.duration_ms, 0)
		self.assertIn("ms", usage.summary())


class TestCliFlags225(unittest.TestCase):
	def test_parser_timeout_safety_sandbox(self):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(
			["--cli", "--timeout", "45", "--safety", "strict", "--sandbox", "docker", "-m", "local-model"]
		)
		mod.prepare_args(args, ["--timeout", "45", "--safety", "strict", "--sandbox", "docker"])
		self.assertEqual(args.timeout, 45)
		self.assertEqual(args.safety, "strict")
		self.assertEqual(args.sandbox_backend, "docker")
		self.assertFalse(args.unsafe)

	def test_no_sandbox_sets_off(self):
		import interpreter as mod

		parser = mod.build_parser()
		args = parser.parse_args(["--cli", "--no-sandbox", "-m", "local-model"])
		mod.prepare_args(args, ["--no-sandbox"])
		self.assertTrue(args.unsafe)
		self.assertEqual(args.sandbox_backend, "none")
		self.assertEqual(args.safety, "off")

	def test_help_documents_flags(self):
		import interpreter as mod

		help_text = mod.build_parser().format_help()
		self.assertIn("--timeout", help_text)
		self.assertIn("--safety", help_text)
		self.assertIn("docker", help_text)


class TestAuditReplCommand(unittest.TestCase):
	def test_audit_command_in_help(self):
		from libs.utility_manager import UtilityManager

		text = UtilityManager().get_help_commands() if hasattr(UtilityManager(), "get_help_commands") else ""
		# Fallback: read the help string builder used by display
		um = UtilityManager()
		help_src = um.__class__.__module__
		from libs import utility_manager as umod

		src = Path(umod.__file__).read_text(encoding="utf-8")
		self.assertIn("/audit", src)


if __name__ == "__main__":
	unittest.main()
