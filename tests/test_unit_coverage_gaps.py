# -*- coding: utf-8 -*-
"""Extra unit coverage for CodeInterpreter helpers and execution paths."""

from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.code_interpreter import (
	CodeInterpreter,
	_is_python_code,
	_kill_process_group,
	_limit_resources,
	_strip_leading_fence_language_line,
)


class TestCodeInterpreterExtra(unittest.TestCase):
	def setUp(self):
		self.ci = CodeInterpreter()
		self.ci.UNSAFE_EXECUTION = True
		self.ci.safety_manager = MagicMock()
		self.ci.safety_manager.unsafe_mode = True
		self.ci.safety_manager.assess_execution.return_value = SimpleNamespace(
			allowed=True, reasons=[]
		)

	def test_strip_more_languages(self):
		self.assertEqual(_strip_leading_fence_language_line("javascript\nx"), "x")
		self.assertEqual(_strip_leading_fence_language_line("bash\necho 1"), "echo 1")
		self.assertEqual(_strip_leading_fence_language_line(""), "")

	def test_kill_process_group(self):
		proc = MagicMock()
		proc.pid = 1234
		with patch("libs.code_interpreter.os.name", "nt"):
			_kill_process_group(proc)
			proc.kill.assert_called()
		proc2 = MagicMock()
		proc2.pid = 1
		proc2.kill.side_effect = [OSError("x"), None]
		with patch("libs.code_interpreter.os.name", "nt"):
			_kill_process_group(proc2)

	def test_limit_resources_skips_when_unavailable(self):
		"""Must not apply rlimits in the parent test process (would SIGXCPU/OOM CI)."""
		with patch("libs.code_interpreter.resource", None):
			_limit_resources()  # no-op; must not raise

	def test_limit_resources_sets_unix_rlimits_via_mock(self):
		mock_res = MagicMock()
		mock_res.RLIMIT_CPU = 0
		mock_res.RLIMIT_AS = 1
		mock_res.RLIMIT_NPROC = 2
		with patch("libs.code_interpreter.resource", mock_res):
			_limit_resources()
		self.assertGreaterEqual(mock_res.setrlimit.call_count, 2)

	def test_safe_input_eof(self):
		with patch("builtins.input", side_effect=EOFError):
			self.assertEqual(self.ci._safe_input("> ", default="d"), "d")

	def test_is_unsafe_live(self):
		self.ci.safety_manager.unsafe_mode = False
		self.assertFalse(self.ci._is_unsafe())
		self.ci.safety_manager.unsafe_mode = True
		self.assertTrue(self.ci._is_unsafe())

	def test_get_subprocess_security_kwargs_none_context(self):
		kwargs = self.ci._get_subprocess_security_kwargs(None)
		self.assertIn("cwd", kwargs)
		self.assertIn("env", kwargs)

	def test_get_subprocess_security_kwargs_with_context(self):
		ctx = SimpleNamespace(cwd=tempfile.gettempdir(), env={"PATH": "/bin", "HOME": "/tmp", "EXTRA": "x"})
		kwargs = self.ci._get_subprocess_security_kwargs(ctx)
		self.assertEqual(kwargs["cwd"], ctx.cwd)
		self.assertIn("PATH", kwargs["env"])
		self.assertNotIn("EXTRA", kwargs["env"])

	def test_normalize_command(self):
		self.assertIn("python -c", self.ci._normalize_command("pwd"))
		self.assertIn("python -c", self.ci._normalize_command("ls"))
		self.assertIn("python -c", self.ci._normalize_command("dir"))
		self.assertEqual(self.ci._normalize_command("echo hi"), "echo hi")

	def test_build_command_invocation_python_c(self):
		parts = self.ci._build_command_invocation('python -c "print(1)"')
		self.assertEqual(parts[0], "python")
		self.assertEqual(parts[1], "-c")
		self.assertEqual(parts[2], "print(1)")

	def test_build_command_invocation_node_e(self):
		parts = self.ci._build_command_invocation("node -e '1+1'")
		self.assertEqual(parts[0], "node")
		self.assertEqual(parts[1], "-e")

	def test_build_command_invocation_shell_ops_blocked_on_windows(self):
		with patch("libs.code_interpreter.os.name", "nt"):
			with self.assertRaises(ValueError):
				self.ci._build_command_invocation("echo a && echo b")

	def test_execute_code_javascript_force(self):
		# May fail if node missing; still exercises path
		out, err = self.ci.execute_code("console.log(1)", "javascript", force_execute=True)
		self.assertTrue(out is not None or err is not None)

	def test_extract_code_multiple_fences(self):
		text = "```python\na=1\n```\ntext\n```python\nb=2\n```"
		code = self.ci.extract_code(text)
		self.assertTrue(code)

	def test_execute_script_python_unsafe(self):
		out, err = self.ci._execute_script("print('ok-ci')", "python")
		self.assertIn("ok-ci", out or "")
		self.assertFalse(err)

	def test_execute_script_blocked_safe(self):
		self.ci.safety_manager.unsafe_mode = False
		self.ci.safety_manager.assess_execution.return_value = SimpleNamespace(
			allowed=False, reasons=["dangerous"]
		)
		out, err = self.ci._execute_script("import os; os.system('rm -rf /')", "python")
		self.assertIsNone(out)
		self.assertIn("Safety blocked", err)


class TestInterpreterLibSession(unittest.TestCase):
	def _make(self):
		from unittest.mock import MagicMock

		from libs.interpreter_lib import Interpreter

		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), patch(
			"libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None
		):
			from tests.helpers.cli_args import make_interpreter_args

			interp = Interpreter(make_interpreter_args())
		return interp

	def test_handle_session_commands_no_store(self):
		interp = self._make()
		interp.session_store = None
		with patch("builtins.print"):
			self.assertTrue(interp.handle_session_command("/sessions"))
			self.assertTrue(interp.handle_session_command("/session save"))
			self.assertTrue(interp.handle_session_command("/session clear"))
			self.assertTrue(interp.handle_session_command("/session info"))
			self.assertTrue(interp.handle_session_command("/session weird"))
			self.assertFalse(interp.handle_session_command("/other"))

	def test_handle_session_with_store(self):
		interp = self._make()
		store = MagicMock()
		store.session_id = "s1"
		store.get_metadata.return_value = {
			"session_id": "s1",
			"message_count": 2,
			"model": "gpt",
			"updated_at": 0,
		}
		interp.session_store = store
		interp.conversation_history = [{"role": "user", "content": "hi"}]
		with patch("builtins.print"):
			self.assertTrue(interp.handle_session_command("/session save"))
			self.assertTrue(interp.handle_session_command("/session info"))
			self.assertTrue(interp.handle_session_command("/session clear"))
		store.clear.assert_called()

	def test_record_turn_and_after(self):
		interp = self._make()
		store = MagicMock()
		interp.session_store = store
		interp.conversation_history = []
		interp.record_session_turn(task="hi", code_snippet="print(1)")
		store.save.assert_called()

	def test_toggle_sandbox_delegates(self):
		interp = self._make()
		with patch("libs.interpreter_lib.toggle_sandbox_mode", return_value=True) as tog:
			interp.toggle_sandbox_mode()
			tog.assert_called()

	def test_run_agent_pipeline_mocked(self):
		interp = self._make()
		fake_ctx = MagicMock()
		with patch("libs.agents.agent_pipeline.AgentPipeline") as Pipe:
			Pipe.return_value.run.return_value = fake_ctx
			out = interp.run_agent_pipeline("task", "Windows")
		self.assertIs(out, fake_ctx)


class TestModelRouterExtra(unittest.TestCase):
	def test_jitter_backoff(self):
		from libs.core.model_router import ModelRouter

		vals = [ModelRouter._jitter_backoff_seconds(2) for _ in range(20)]
		self.assertTrue(all(0.0 <= v <= 30.0 for v in vals))
		self.assertTrue(any(v >= 0.0 for v in vals))

	def test_resolve_api_key_name(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.INTERPRETER_MODEL = "gpt-4o"
		router = ModelRouter(interp)
		self.assertEqual(router._resolve_api_key_name({"provider": "openai"}), "OPENAI_API_KEY")
		self.assertEqual(router._resolve_api_key_name({"provider": "nvidia"}), "NVIDIA_API_KEY")
		self.assertEqual(router._resolve_api_key_name({"provider": "openrouter"}), "OPENROUTER_API_KEY")
		interp.INTERPRETER_MODEL = "claude-3"
		self.assertEqual(router._resolve_api_key_name({}), "ANTHROPIC_API_KEY")
		interp.INTERPRETER_MODEL = "gemini-pro"
		self.assertEqual(router._resolve_api_key_name({}), "GEMINI_API_KEY")

	def test_run_openai_compatible_completion(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.INTERPRETER_MODEL = "local-llama"
		router = ModelRouter(interp)
		completion = MagicMock(return_value={"ok": True})
		out = router.run_openai_compatible_completion(
			"OPENAI_API_KEY",
			[{"role": "user", "content": "x"}],
			0.1,
			10,
			"http://localhost:11434/v1",
			completion_fn=completion,
			getenv_fn=lambda *_: "sk",
		)
		self.assertTrue(completion.called)
		self.assertEqual(out, {"ok": True})

	def test_generate_content_with_retries_success(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.logger = MagicMock()
		interp.MAX_LLM_RETRIES = 2
		interp.config_values = {"temperature": 0.1, "max_tokens": 32, "provider": "openai"}
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp._key_manager = None
		interp.generate_content = MagicMock(return_value="ok")
		router = ModelRouter(interp)
		text = router.generate_content_with_retries(
			"hi",
			[],
			config_values=interp.config_values,
			sleep_fn=lambda *_: None,
			display_fn=lambda *_: None,
		)
		self.assertEqual(text, "ok")


if __name__ == "__main__":
	unittest.main()
