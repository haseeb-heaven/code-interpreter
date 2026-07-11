"""Unit tests for AutonomousAgentLoop (#215)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from libs.agent.auto_loop import AutonomousAgentLoop
from libs.tools.bootstrap import build_native_fs_registry


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


class TestAutonomousAgentLoop(unittest.TestCase):
	def test_final_answer_without_tools(self):
		def completion_fn(model, messages, tools):
			return _FakeResponse(_FakeMessage(content="done"))

		loop = AutonomousAgentLoop(
			model="test-model",
			auto_mode=True,
			completion_fn=completion_fn,
			registry=build_native_fs_registry(),
		)
		self.assertEqual(loop.run("say hi"), "done")

	def test_tool_call_then_final_answer_yolo(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			registry = build_native_fs_registry(cwd=tmpdir, restrict_to_cwd=True)
			target = Path(tmpdir) / "out.txt"
			state = {"step": 0}

			def completion_fn(model, messages, tools):
				state["step"] += 1
				if state["step"] == 1:
					return _FakeResponse(
						_FakeMessage(
							content=None,
							tool_calls=[
								_FakeToolCall(
									"write_file",
									'{"path": "%s", "content": "from-loop"}'
									% str(target).replace("\\", "\\\\"),
								)
							],
						)
					)
				return _FakeResponse(_FakeMessage(content="wrote file"))

			loop = AutonomousAgentLoop(
				model="test-model",
				auto_mode=True,
				completion_fn=completion_fn,
				registry=registry,
			)
			result = loop.run("write a file")
			self.assertEqual(result, "wrote file")
			self.assertTrue(target.is_file())
			self.assertEqual(target.read_text(encoding="utf-8"), "from-loop")

	def test_denied_tool_call_in_non_auto_mode(self):
		calls = {"n": 0}

		def completion_fn(model, messages, tools):
			calls["n"] += 1
			if calls["n"] == 1:
				return _FakeResponse(
					_FakeMessage(
						content=None,
						tool_calls=[_FakeToolCall("list_dir", '{"path": "."}')],
					)
				)
			# After denial, final answer
			return _FakeResponse(_FakeMessage(content="aborted"))

		loop = AutonomousAgentLoop(
			model="test-model",
			auto_mode=False,
			completion_fn=completion_fn,
			confirm_fn=lambda name, args: False,
			registry=build_native_fs_registry(),
		)
		self.assertEqual(loop.run("list files"), "aborted")


if __name__ == "__main__":
	unittest.main()
