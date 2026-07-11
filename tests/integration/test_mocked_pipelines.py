"""Integration tests: end-to-end agent pipeline + main loop with mocked LLM."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.agents.base_agent import AgentContext
from libs.agents.agent_pipeline import AgentPipeline
from libs.core.main_loop import run_interpreter_main


class TestAgentPipelineIntegration(unittest.TestCase):
	def test_pipeline_happy_path_with_stubbed_stages(self):
		"""Stub each pipeline stage collaborator and assert approved context."""
		model_router = MagicMock()
		executor = MagicMock()
		repairer = MagicMock()
		prompt_builder = MagicMock()
		logger = MagicMock()

		pipeline = AgentPipeline(
			model_router=model_router,
			executor=executor,
			repairer=repairer,
			prompt_builder=prompt_builder,
			logger=logger,
			unsafe=False,
		)

		pipeline.intent_router.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "intent", "code") or ctx
		)
		pipeline.planner.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "plan", ["print"]) or ctx
		)
		pipeline.executor.generate = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "code", "print('hello')") or ctx
		)
		pipeline.safety_guard.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "safe", True) or ctx
		)
		pipeline.executor.execute = MagicMock(
			side_effect=lambda ctx: (
				setattr(ctx, "output", "hello"),
				setattr(ctx, "error", ""),
				ctx,
			)[-1]
		)
		pipeline.repairer.run = MagicMock(side_effect=lambda ctx: ctx)
		pipeline.verifier.run = MagicMock(
			side_effect=lambda ctx: setattr(ctx, "verified", True) or ctx
		)
		pipeline.reviewer.run = MagicMock(
			side_effect=lambda ctx: (
				setattr(ctx, "approved", True),
				ctx.metadata.update({"review_reason": "ok"}),
				ctx,
			)[-1]
		)

		result = pipeline.run(task="print hello", os_name="Windows", language="python")
		self.assertEqual(result.intent, "code")
		self.assertEqual(result.code, "print('hello')")
		self.assertEqual(result.output, "hello")
		self.assertTrue(result.verified)
		self.assertTrue(result.approved)


class TestMainLoopFileAgentIntegration(unittest.TestCase):
	def test_file_yes_agent_pipeline_oneshot(self):
		with tempfile.TemporaryDirectory() as tmp:
			task_path = Path(tmp) / "task.txt"
			task_path.write_text("print hello", encoding="utf-8")

			interp = MagicMock()
			interp.args = MagicMock(file=str(task_path))
			interp.INTERPRETER_PROMPT_FILE = True
			interp.INTERPRETER_PROMPT_INPUT = False
			interp.AUTO_YES = True
			interp.AGENT_MODE = True
			interp.SCRIPT_MODE = False
			interp.COMMAND_MODE = False
			interp.VISION_MODE = False
			interp.CHAT_MODE = False
			interp.INTERPRETER_MODE = "code"
			interp.INTERPRETER_LANGUAGE = "python"
			interp.INTERPRETER_MODEL = "gpt-4o"
			interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
			interp.UNSAFE_EXECUTION = False
			interp.DISPLAY_CODE = False
			interp.SAVE_CODE = False
			interp.EXECUTE_CODE = False
			interp.config_values = {"start_sep": "```", "end_sep": "```"}
			interp.logger = MagicMock()
			interp.console = MagicMock()
			interp.utility_manager = MagicMock()
			interp.utility_manager.get_os_platform.return_value = ("Windows",)
			interp.utility_manager.read_file.return_value = "print hello"
			interp.utility_manager.extract_file_name.return_value = None
			interp.history_manager = MagicMock()
			interp.package_manager = MagicMock()
			interp._structured_output_active.return_value = False
			interp._safe_input.side_effect = AssertionError("input must not be called")
			interp._display_session_banner = MagicMock()
			interp._is_recoverable_runtime_error.return_value = False
			interp.run_agent_pipeline.return_value = AgentContext(
				task="print hello",
				os_name="Windows",
				language="python",
				intent="code",
				plan=["step"],
				code="print(1)",
				output="1\n",
				safe=True,
				verified=True,
				approved=True,
				metadata={"mode": "code", "review_reason": "ok"},
			)

			with patch("libs.interpreter_lib.display_markdown_message"), \
			     patch("libs.interpreter_lib.display_code"):
				run_interpreter_main(interp, "3.3.0")

			interp.run_agent_pipeline.assert_called_once()


if __name__ == "__main__":
	unittest.main()
