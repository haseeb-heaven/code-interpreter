"""Regression tests for the Groq ``tool_use_failed`` / "Tool choice is none,
but model called a tool" BadRequestError.

Bug: during a ``--agentic`` ReAct run against a Groq-hosted OSS model (e.g.
``groq/openai/gpt-oss-20b``), the model can spontaneously emit a tool call on
a turn that carried no ``tools`` (i.e. an effective ``tool_choice="none"``).
Groq's backend rejects that outright with::

    litellm.BadRequestError: GroqException - {"error":{"message":
    "Tool choice is none, but model called a tool","type":
    "invalid_request_error","code":"tool_use_failed", ...}}

Previously this propagated straight out of ``complete_with_free_fallback``
and killed the whole ReAct workflow (``Status: FAILED``) on a single bad
turn. These tests assert the controller instead resamples once and keeps
going.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import litellm

from libs.agent.llm import call_llm, complete_with_free_fallback
from libs.agent.react_controller import ReActController
from libs.free_llms import FreeModelsExhaustedError, is_tool_choice_none_conflict


def _tool_choice_conflict_error() -> litellm.BadRequestError:
	"""Build the exact exception Groq raises for this bug (see module docstring)."""
	message = (
		'GroqException - {"error":{"message":"Tool choice is none, but model '
		'called a tool","type":"invalid_request_error","code":"tool_use_failed",'
		'"failed_generation":"{\\"name\\": \\"assistant\\", \\"arguments\\": '
		'{\\"instruction\\":\\"Modify create_charts to save plots to files '
		'instead of showing, and run the script.\\"}}"}}'
	)
	return litellm.BadRequestError(
		message=message,
		model="groq/openai/gpt-oss-20b",
		llm_provider="groq",
	)


def _ok_response(content: str) -> SimpleNamespace:
	return SimpleNamespace(
		choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
		usage=SimpleNamespace(total_tokens=5),
	)


class TestIsToolChoiceNoneConflict(unittest.TestCase):
	def test_matches_groq_error_signature(self):
		self.assertTrue(is_tool_choice_none_conflict(_tool_choice_conflict_error()))

	def test_does_not_match_unrelated_errors(self):
		self.assertFalse(is_tool_choice_none_conflict(RuntimeError("network down")))
		self.assertFalse(is_tool_choice_none_conflict(RuntimeError("rate limit exceeded")))


class TestCompleteWithFreeFallbackToolChoiceConflict(unittest.TestCase):
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_resamples_once_then_succeeds(self, completion_mock, _cost):
		completion_mock.side_effect = [
			_tool_choice_conflict_error(),
			_ok_response("Thought: ok\nAction: finish\nAction Input: {}\n"),
		]
		sleep_fn = MagicMock()

		content, metrics = call_llm(
			"gpt-4o",
			[{"role": "user", "content": "hi"}],
			enable_free_fallback=False,
			sleep_fn=sleep_fn,
		)

		self.assertIn("finish", content)
		self.assertEqual(completion_mock.call_count, 2)
		# Not a rate limit: no sleep should have been injected before the retry.
		sleep_fn.assert_not_called()

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_persistent_conflict_raises_after_single_retry(self, completion_mock, _cost):
		completion_mock.side_effect = [
			_tool_choice_conflict_error(),
			_tool_choice_conflict_error(),
		]

		with self.assertRaises(litellm.BadRequestError):
			complete_with_free_fallback(
				"gpt-4o",
				[{"role": "user", "content": "hi"}],
				enable_free_fallback=False,
				sleep_fn=MagicMock(),
			)
		# Exactly one retry (2 total attempts) — a single bad turn should not
		# be retried indefinitely.
		self.assertEqual(completion_mock.call_count, 2)

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_falls_back_to_next_candidate_when_enabled(self, completion_mock, _cost):
		completion_mock.side_effect = [
			_tool_choice_conflict_error(),
			_tool_choice_conflict_error(),
			_ok_response("done via backup"),
		]
		fake_catalog = MagicMock()
		with patch(
			"libs.agent.llm.free_fallback_candidates",
			return_value=[{"config": "backup", "model": "backup-model", "provider": ""}],
		):
			response, metrics = complete_with_free_fallback(
				"gpt-4o",
				[{"role": "user", "content": "hi"}],
				enable_free_fallback=True,
				catalog=fake_catalog,
				sleep_fn=MagicMock(),
			)
		# Primary retried once (2 attempts), then fell through to the backup
		# candidate on the 3rd call instead of aborting the whole run.
		self.assertEqual(completion_mock.call_count, 3)
		self.assertEqual(metrics["model_used"], "backup-model")
		self.assertEqual(response.choices[0].message.content, "done via backup")

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_exhausted_with_fallback_enabled_raises_clean_error(self, completion_mock, _cost):
		"""No further candidates available even with fallback enabled: the raw
		litellm exception is wrapped into the friendlier FreeModelsExhaustedError
		instead of a bare traceback."""
		completion_mock.side_effect = [
			_tool_choice_conflict_error(),
			_tool_choice_conflict_error(),
		]
		with patch("libs.agent.llm.free_fallback_candidates", return_value=[]):
			with self.assertRaises(FreeModelsExhaustedError):
				complete_with_free_fallback(
					"gpt-4o",
					[{"role": "user", "content": "hi"}],
					enable_free_fallback=True,
					sleep_fn=MagicMock(),
				)
		self.assertEqual(completion_mock.call_count, 2)

	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_tool_choice_none_never_sends_tools(self, completion_mock, _cost):
		completion_mock.return_value = _ok_response("done")

		complete_with_free_fallback(
			"gpt-4o",
			[{"role": "user", "content": "hi"}],
			tools=[{"type": "function", "function": {"name": "noop"}}],
			tool_choice="none",
			enable_free_fallback=False,
			sleep_fn=MagicMock(),
		)

		_, kwargs = completion_mock.call_args
		self.assertNotIn("tools", kwargs)
		self.assertNotIn("tool_choice", kwargs)


class TestReActControllerSurvivesToolChoiceConflict(unittest.TestCase):
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_run_completes_after_one_bad_turn(self, completion_mock, _cost):
		"""End-to-end: the exact reported error on the first controller turn
		must not abort the whole ReAct run."""
		completion_mock.side_effect = [
			_tool_choice_conflict_error(),
			_ok_response('Thought: done\nAction: finish\nAction Input: {"summary": "ok"}\n'),
		]

		with tempfile.TemporaryDirectory() as tmp:
			code_interpreter = MagicMock()
			safety = MagicMock()
			controller = ReActController(
				model_name="gpt-4o",
				api_key=None,
				code_interpreter=code_interpreter,
				safety_manager=safety,
				log_path=os.path.join(tmp, "agent_react.jsonl"),
				max_steps=5,
				quiet_ui=True,
			)
			final = controller.run("Modify create_charts to save plots to files")

		self.assertEqual(final["status"], "COMPLETED")
		self.assertEqual(completion_mock.call_count, 2)


if __name__ == "__main__":
	unittest.main()
