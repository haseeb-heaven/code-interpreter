"""Unit tests for AutonomousAgentLoop (#215)."""

from __future__ import annotations

import json
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

	def test_malformed_tool_xml_triggers_repair_not_finish(self):
		"""Groq-style dumped <write_file ...</function> must retry, not exit."""
		from libs.agent.auto_loop import looks_like_malformed_tool_markup

		bad = (
			'<write_file {"content": "x,y\\n1,10", "path": "D:\\\\tmp\\\\dummy_data.txt"}'
			"</function>\n"
			'<run_shell {"command": "python -c \\"import matplotlib\\""}</function>'
		)
		self.assertTrue(looks_like_malformed_tool_markup(bad))

		with tempfile.TemporaryDirectory() as tmpdir:
			registry = build_native_fs_registry(cwd=tmpdir, restrict_to_cwd=True)
			target = Path(tmpdir) / "chart_ok.txt"
			calls = {"n": 0}
			seen_repair = {"ok": False}

			def completion_fn(model, messages, tools):
				calls["n"] += 1
				for msg in messages:
					content = msg.get("content") or ""
					if "proper tool_calls" in content.lower() or "valid tool" in content.lower():
						seen_repair["ok"] = True
				if calls["n"] == 1:
					return _FakeResponse(_FakeMessage(content=bad, tool_calls=None))
				if calls["n"] == 2:
					# After repair: emit a real structured tool call.
					return _FakeResponse(
						_FakeMessage(
							content=None,
							tool_calls=[
								_FakeToolCall(
									"write_file",
									json.dumps({"path": str(target), "content": "ok"}),
								)
							],
						)
					)
				return _FakeResponse(_FakeMessage(content="charts written to D:\\tmp"))

			loop = AutonomousAgentLoop(
				model="test-model",
				auto_mode=True,
				completion_fn=completion_fn,
				registry=registry,
				max_iterations=10,
			)
			result = loop.run("Create 3 chart PNGs under D:\\tmp from dummy_data.txt")
			self.assertGreaterEqual(calls["n"], 3, "must repair then tool-call then finish")
			self.assertTrue(seen_repair["ok"], "must inject a repair prompt")
			self.assertEqual(result, "charts written to D:\\tmp")
			self.assertTrue(target.is_file())
			self.assertFalse(looks_like_malformed_tool_markup(result))

	def test_malformed_tool_xml_exhausts_repairs_without_returning_markup(self):
		"""If every turn dumps broken tags, keep repairing up to the cap then stop cleanly."""
		bad = '<write_file {"path": "x.txt", "content": "hi"}</function>'
		calls = {"n": 0}

		def completion_fn(model, messages, tools):
			calls["n"] += 1
			return _FakeResponse(_FakeMessage(content=bad, tool_calls=None))

		loop = AutonomousAgentLoop(
			model="test-model",
			auto_mode=True,
			completion_fn=completion_fn,
			registry=build_native_fs_registry(),
			max_iterations=20,
		)
		result = loop.run("write a file")
		self.assertGreaterEqual(calls["n"], 3)
		# Must not hand the raw malformed XML back as a "final answer".
		self.assertNotIn("<write_file", result)


if __name__ == "__main__":
	unittest.main()
