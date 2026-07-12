# -*- coding: utf-8 -*-
"""ReAct / AutoLoop wiring for missing-binary recovery (mocked)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.agent.auto_loop import AutonomousAgentLoop
from libs.agent.react_controller import ReActController
from libs.agent.step_ui import NullStepPresenter
from libs.deps.install_flow import HandleResult, MissingBinaryHandler
from libs.deps.missing_binary import detect_missing_binary


class _FakeFn:
	def __init__(self, name, arguments, call_id="call_1"):
		self.name = name
		self.arguments = arguments
		self._id = call_id


class _FakeToolCall:
	def __init__(self, name, arguments, call_id="call_1"):
		self.id = call_id
		self.function = _FakeFn(name, arguments, call_id)
		self.type = "function"


class _FakeMessage:
	def __init__(self, content=None, tool_calls=None):
		self.content = content
		self.tool_calls = tool_calls


class _FakeChoice:
	def __init__(self, message):
		self.message = message


class _FakeResponse:
	def __init__(self, message):
		self.choices = [_FakeChoice(message)]


class TestReActMissingBinaryRecovery(unittest.TestCase):
	def test_recover_appends_handler_observation(self):
		handler = MissingBinaryHandler(
			confirm_fn=lambda p: False,
			search_fn=None,
			install_fn=None,
		)
		ctrl = ReActController(
			model_name="test",
			code_interpreter=MagicMock(),
			safety_manager=MagicMock(),
			quiet_ui=True,
			step_presenter=NullStepPresenter(),
			missing_binary_handler=handler,
		)
		obs = ctrl._recover_missing_binary("ERROR: ffmpeg: command not found")
		self.assertIn("MISSING_TOOL", obs)
		self.assertIn("ffmpeg", obs.lower())
		self.assertIn("declined", obs.lower())


class TestAutoLoopMissingBinaryRecovery(unittest.TestCase):
	def test_shell_error_triggers_handler(self):
		registry = MagicMock()
		registry.openai_schemas.return_value = []
		tool_result = MagicMock()
		tool_result.success = False
		tool_result.error = "ffmpeg: command not found"
		tool_result.output = ""
		registry.dispatch.return_value = tool_result

		handled = []

		class RecordingHandler(MissingBinaryHandler):
			def handle(self, error_text, *, auto_yes=False, yolo=False, do_search=False):
				handled.append(error_text)
				return HandleResult(
					detected=True,
					binary=detect_missing_binary(error_text),
					installed=False,
					observation="MISSING_TOOL: user declined",
					skipped=True,
				)

		state = {"n": 0}

		def completion_fn(model, messages, tools):
			state["n"] += 1
			if state["n"] == 1:
				return _FakeResponse(
					_FakeMessage(
						content="I'll run ffmpeg",
						tool_calls=[
							_FakeToolCall("run_shell", '{"command": "ffmpeg -version"}'),
						],
					)
				)
			return _FakeResponse(_FakeMessage(content="done after missing tool"))

		loop = AutonomousAgentLoop(
			model="test",
			auto_mode=True,
			completion_fn=completion_fn,
			registry=registry,
			quiet_ui=True,
			step_presenter=NullStepPresenter(),
			missing_binary_handler=RecordingHandler(confirm_fn=lambda p: False),
		)
		out = loop.run("trim video")
		self.assertEqual(out, "done after missing tool")
		self.assertTrue(handled)
		self.assertIn("ffmpeg", handled[0].lower())


if __name__ == "__main__":
	unittest.main()
