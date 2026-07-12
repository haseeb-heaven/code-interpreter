"""Regression tests for the ``--agentic`` rate-limit fallback bug.

Bug report: on a real ``--agentic --yes -m openrouter-free`` run, the primary
model correctly fell back from ``openrouter/free`` to
``groq/llama-3.1-8b-instant``, then that Groq candidate got persistently
rate-limited (429) on every subsequent LLM call. The run eventually printed
``Status: FAILED`` with **no explanation at all** on the console.

Root cause (confirmed via reproduction, see systematic-debugging investigation):
``complete_with_free_fallback`` / ``free_fallback_candidates`` already rotate
correctly through the free catalog on persistent rate limits and raise a
clear ``FreeModelsExhaustedError`` when every candidate is exhausted (see
``CandidateRotationOnPersistentRateLimitTests`` below — this already worked
before this fix and is locked in here as a regression guard).

The actual gap was in ``ReActController._repair_parse``: when the model's
Thought/Action output failed to parse (``ParseError``), the controller asks
the model to reformat it. That *repair* LLM call reuses the same
free-fallback machinery and can itself hit persistent rate-limiting and
raise ``FreeModelsExhaustedError``. ``_repair_parse`` used to catch **any**
exception from that repair call and swallow it by returning ``None``, so
``ReActController.run()`` reported the ORIGINAL (now irrelevant) parse error
as ``failure_reason`` -- which is never even printed to the console (only
Status/Steps/Tokens/Cost are) -- producing exactly the observed silent
``Status: FAILED``. ``ParseAndFallbackErrorSwallowedRegressionTests`` below
pins the fix: the repair call's LLM-layer failure must be reported via the
same friendly ``_report_llm_failure`` path used everywhere else.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import litellm

from libs.agent.llm import complete_with_free_fallback
from libs.agent.react_controller import ReActController
from libs.free_llms import FreeModelsExhaustedError

GROQ_429 = (
	"litellm.RateLimitError: RateLimitError: GroqException - "
	'{"error":{"message":"Rate limit reached for model `llama-3.1-8b-instant` '
	"in organization org_test on tokens per minute (TPM): Limit 6000, Used 5990, "
	'Requested 50. Please try again in 2.5s. Visit https://console.groq.com/docs/rate-limits '
	'for more information.","type":"tokens","code":"rate_limit_exceeded"}}'
)


def _groq_rate_limit_error(model: str = "groq/llama-3.1-8b-instant") -> litellm.RateLimitError:
	return litellm.RateLimitError(message=GROQ_429, model=model, llm_provider="groq")


class CandidateRotationOnPersistentRateLimitTests(unittest.TestCase):
	"""Lock in existing (already-correct) rotation/exhaustion behavior in
	``complete_with_free_fallback`` against the real ``configs/models.toml``
	free catalog, using the exact scenario from the bug report."""

	@patch("libs.agent.llm.time.sleep", MagicMock())
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_persistent_rate_limit_rotates_to_next_candidate_then_succeeds(
		self, completion_mock, _cost
	):
		"""A candidate rate-limited beyond its retry budget must rotate to the
		next free-catalog candidate instead of aborting the whole call."""
		from types import SimpleNamespace

		ok = SimpleNamespace(
			choices=[SimpleNamespace(message=SimpleNamespace(content="ok-from-fallback"))],
			usage=SimpleNamespace(total_tokens=5),
		)

		def side_effect(**kwargs):
			model = kwargs.get("model")
			if model == "groq/llama-3.1-8b-instant":
				raise _groq_rate_limit_error(model)
			return ok

		completion_mock.side_effect = side_effect

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			response, metrics = complete_with_free_fallback(
				"groq/llama-3.1-8b-instant",
				[{"role": "user", "content": "hi"}],
			)

		self.assertEqual(response.choices[0].message.content, "ok-from-fallback")
		self.assertNotEqual(metrics["model_used"], "groq/llama-3.1-8b-instant")
		self.assertEqual(metrics["fallback_used"], 1.0)
		# Retried the rate-limited candidate (DEFAULT_RATE_LIMIT_RETRIES=2) before
		# rotating away from it.
		attempted_models = [c.kwargs.get("model") for c in completion_mock.call_args_list]
		self.assertEqual(attempted_models.count("groq/llama-3.1-8b-instant"), 3)

	@patch("libs.agent.llm.time.sleep", MagicMock())
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_all_candidates_rate_limited_raises_clear_exhaustion_error(
		self, completion_mock, _cost
	):
		"""When every free-catalog candidate is persistently rate-limited, the
		call must raise a CLEAR ``FreeModelsExhaustedError`` (not a bare/opaque
		failure) naming every model that was tried."""

		def side_effect(**kwargs):
			raise _groq_rate_limit_error(kwargs.get("model"))

		completion_mock.side_effect = side_effect

		with patch.dict(
			os.environ,
			{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
			clear=False,
		):
			with self.assertRaises(FreeModelsExhaustedError) as ctx:
				complete_with_free_fallback(
					"groq/llama-3.1-8b-instant",
					[{"role": "user", "content": "hi"}],
				)

		message = str(ctx.exception)
		self.assertIn("groq-llama-3.1-8b", message)
		self.assertIn("/free", message)
		self.assertIn("/model", message)
		# Must have actually rotated through multiple distinct candidates, not
		# just given up on the first one.
		attempted_models = {c.kwargs.get("model") for c in completion_mock.call_args_list}
		self.assertGreater(len(attempted_models), 1)


class ParseAndFallbackErrorSwallowedRegressionTests(unittest.TestCase):
	"""Regression tests for the actual root cause: ``_repair_parse`` silently
	discarding an LLM-layer failure (e.g. rate-limit exhaustion) that happens
	during a parse-repair attempt."""

	def _run_controller(self, call_llm_side_effect, max_steps=5):
		with tempfile.TemporaryDirectory() as tmp:
			controller = ReActController(
				model_name="groq/llama-3.1-8b-instant",
				code_interpreter=MagicMock(),
				safety_manager=MagicMock(),
				log_path=os.path.join(tmp, "agent_react.jsonl"),
				max_steps=max_steps,
				auto_yes=True,
				quiet_ui=True,
			)
			with patch(
				"libs.agent.react_controller.call_llm", side_effect=call_llm_side_effect
			):
				return controller.run("create 3 different charts and show")

	def test_exhaustion_during_repair_reports_clear_message_not_parse_error(self):
		"""Bug reproduction: the FIRST think() call produces unparseable output
		(triggering a repair attempt), and the repair attempt's own LLM call
		exhausts every free-catalog candidate. The reported failure must be the
		real (clear) exhaustion message -- not a misleading 'Parse error'."""
		calls = {"n": 0}
		exhausted = FreeModelsExhaustedError(
			"All free / cheap models failed after trying: groq-llama-3.1-8b "
			"(groq/llama-3.1-8b-instant), groq-gemma (groq/openai/gpt-oss-20b). "
			"Last error: rate limited. Use /free to list presets or /model "
			"<name> to switch models.",
			tried=["groq-llama-3.1-8b", "groq-gemma"],
			last_error=_groq_rate_limit_error(),
		)

		def call_llm_side_effect(model_name, messages, api_key, **kwargs):
			calls["n"] += 1
			if calls["n"] == 1:
				return "this is not a valid ReAct step at all", {"cost": 0.0, "tokens": 1}
			raise exhausted

		state = self._run_controller(call_llm_side_effect)

		self.assertEqual(state["status"], "FAILED")
		self.assertNotIn("Parse error", state["failure_reason"])
		self.assertIn("All free / cheap models failed", state["failure_reason"])
		self.assertIn("/free", state["failure_reason"])
		self.assertIn("/model", state["failure_reason"])
		self.assertEqual(calls["n"], 2)

	def test_double_parse_failure_without_llm_error_still_reports_parse_error(self):
		"""Regression guard: when the repair attempt's output is ALSO
		unparseable (no LLM/rate-limit error involved), behavior is unchanged
		-- report the original parse error, exactly like before this fix."""

		def call_llm_side_effect(model_name, messages, api_key, **kwargs):
			return "still not a valid step either", {"cost": 0.0, "tokens": 1}

		state = self._run_controller(call_llm_side_effect, max_steps=3)

		self.assertEqual(state["status"], "FAILED")
		self.assertIn("Parse error", state["failure_reason"])

	def test_repair_succeeds_normally_after_one_bad_turn(self):
		"""Regression guard: a single bad turn that repairs successfully (no
		LLM error) must let the run continue as before."""
		calls = {"n": 0}

		def call_llm_side_effect(model_name, messages, api_key, **kwargs):
			calls["n"] += 1
			if calls["n"] == 1:
				return "garbage output", {"cost": 0.0, "tokens": 1}
			return (
				'Thought: done\nAction: finish\nAction Input: {"summary": "ok"}\n',
				{"cost": 0.0, "tokens": 2},
			)

		state = self._run_controller(call_llm_side_effect)

		self.assertEqual(state["status"], "COMPLETED")
		self.assertEqual(calls["n"], 2)


class ReActControllerEndToEndRateLimitTests(unittest.TestCase):
	"""End-to-end reproduction of the exact reported scenario against the
	real ``configs/models.toml`` catalog: a fallback-rotated candidate
	(``groq/llama-3.1-8b-instant``) gets persistently rate-limited on a later
	step, and every remaining free-catalog candidate is rate-limited too."""

	@patch("libs.agent.llm.time.sleep", MagicMock())
	@patch("libs.agent.llm.litellm.completion_cost", return_value=0.0)
	@patch("libs.agent.llm.litellm.completion")
	def test_persistent_rate_limit_ends_with_clear_message_not_silent_failed(
		self, completion_mock, _cost
	):
		def side_effect(**kwargs):
			raise _groq_rate_limit_error(kwargs.get("model"))

		completion_mock.side_effect = side_effect

		with tempfile.TemporaryDirectory() as tmp:
			with patch.dict(
				os.environ,
				{"OPENROUTER_API_KEY": "sk-or-test", "GROQ_API_KEY": "gsk-test"},
				clear=False,
			):
				controller = ReActController(
					model_name="groq/llama-3.1-8b-instant",
					code_interpreter=MagicMock(),
					safety_manager=MagicMock(),
					log_path=os.path.join(tmp, "agent_react.jsonl"),
					max_steps=5,
					auto_yes=True,
					quiet_ui=True,
				)
				state = controller.run(
					'"D:\\tmp\\dummy_data.txt" create 3 different charts for this now and show'
				)

		self.assertEqual(state["status"], "FAILED")
		self.assertNotEqual(state["failure_reason"], "")
		self.assertNotIn("max_steps exceeded", state["failure_reason"])
		self.assertNotIn("stagnation", state["failure_reason"])
		self.assertIn("free", state["failure_reason"].lower())
		self.assertTrue(
			"/model" in state["failure_reason"] or "/free" in state["failure_reason"]
		)


if __name__ == "__main__":
	unittest.main()
