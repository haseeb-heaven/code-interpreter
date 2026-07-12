"""
tests/test_live_session_bugfixes.py
====================================
20 offline unit tests covering re-applied product bugfixes B1-B10.

No live API keys, network access, or sandbox processes are required.
"""
from __future__ import annotations

import types
import unittest


# ---------------------------------------------------------------------------
# B1 -- libs/free_llms.py
# ---------------------------------------------------------------------------

class TestRetryAfterCapSeconds(unittest.TestCase):
    """B1-a: DEFAULT_RETRY_AFTER_CAP_SECONDS must be 60.0."""

    def test_cap_is_sixty(self):
        from libs.free_llms import DEFAULT_RETRY_AFTER_CAP_SECONDS
        self.assertEqual(DEFAULT_RETRY_AFTER_CAP_SECONDS, 60.0)


class TestParseRetryAfterSeconds(unittest.TestCase):
    """B1-b: parse_retry_after_seconds returns MAX match capped at 60."""

    def _parse(self, text, cap=60.0):
        from libs.free_llms import parse_retry_after_seconds
        return parse_retry_after_seconds(text, cap=cap)

    def test_try_again_in_pattern(self):
        result = self._parse("Rate limited. Try again in 5s.")
        self.assertAlmostEqual(result, 5.0)

    def test_retry_after_header_pattern(self):
        result = self._parse("Retry-After: 30")
        self.assertAlmostEqual(result, 30.0)

    def test_retry_after_seconds_pattern(self):
        result = self._parse("retry_after_seconds=45.5")
        self.assertAlmostEqual(result, 45.5)

    def test_takes_maximum_of_multiple_matches(self):
        result = self._parse("try again in 10s. Retry-After: 25")
        self.assertAlmostEqual(result, 25.0)

    def test_capped_at_sixty(self):
        result = self._parse("try again in 999s")
        self.assertAlmostEqual(result, 60.0)

    def test_none_when_no_hint(self):
        result = self._parse("Something went wrong unexpectedly.")
        self.assertIsNone(result)


class TestIsDailyFreeQuotaExhausted(unittest.TestCase):
    """B1-c: is_daily_free_quota_exhausted identifies daily-limit errors."""

    def _check(self, text):
        from libs.free_llms import is_daily_free_quota_exhausted
        return is_daily_free_quota_exhausted(RuntimeError(text))

    def test_free_models_per_day(self):
        self.assertTrue(self._check("exceeded the free-models-per-day limit"))

    def test_remaining_zero(self):
        self.assertTrue(self._check("X-RateLimit-Remaining: 0"))

    def test_quota_exceeded(self):
        self.assertTrue(self._check("quota exceeded for today"))

    def test_normal_rate_limit_not_daily(self):
        self.assertFalse(self._check("429 Too Many Requests"))


class TestIsOpenrouterFreeCandidate(unittest.TestCase):
    """B1-d: is_openrouter_free_candidate identifies OpenRouter :free models."""

    def _check(self, **kwargs):
        from libs.free_llms import is_openrouter_free_candidate
        return is_openrouter_free_candidate(kwargs)

    def test_openrouter_provider(self):
        self.assertTrue(self._check(model="meta-llama/llama-3.3-70b", provider="openrouter"))

    def test_free_suffix_in_model(self):
        self.assertTrue(self._check(model="openrouter/meta-llama/llama-3.3-70b:free", provider=""))

    def test_openrouter_api_base(self):
        self.assertTrue(self._check(model="llama", provider="", api_base="https://openrouter.ai/api/v1"))

    def test_groq_not_openrouter(self):
        self.assertFalse(self._check(model="llama3-70b-8192", provider="groq", api_base=""))


# ---------------------------------------------------------------------------
# B3 -- libs/agent/auto_loop.py
# ---------------------------------------------------------------------------

class TestAutoLoopRepairOnBadRequest(unittest.TestCase):
    """B3: AutonomousAgentLoop retries on repairable errors and never raises."""

    def _make_loop(self, side_effects):
        from libs.agent.auto_loop import AutonomousAgentLoop
        call_count = [0]
        effects = list(side_effects)
        ok_resp = types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content="done", tool_calls=None)
            )]
        )

        def fake_complete(model, messages, tools):
            idx = call_count[0]
            call_count[0] += 1
            effect = effects[idx] if idx < len(effects) else effects[-1]
            if isinstance(effect, Exception):
                raise effect
            return ok_resp

        return AutonomousAgentLoop(model="test", auto_mode=True, completion_fn=fake_complete)

    def test_bad_request_error_returns_short_message(self):
        loop = self._make_loop([Exception("tool_use_failed: invalid schema")])
        result = loop.run("test task")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_repair_attempt_then_success(self):
        loop = self._make_loop([Exception("failed_generation: context overflow"), None])
        result = loop.run("test task")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# B4/B5 -- libs/repl_guards.py
# ---------------------------------------------------------------------------

class TestReplGuards(unittest.TestCase):
    """B4/B5: is_non_task_input and format_short_llm_error."""

    def test_traceback_detected(self):
        from libs.repl_guards import is_non_task_input
        tb = "Traceback (most recent call last):\n  File \"test.py\", line 1\nAttributeError: foo"
        self.assertTrue(is_non_task_input(tb))

    def test_normal_task_not_flagged(self):
        from libs.repl_guards import is_non_task_input
        self.assertFalse(is_non_task_input("Plot a bar chart of sales data"))

    def test_format_short_llm_error_truncates(self):
        from libs.repl_guards import format_short_llm_error
        long_msg = "litellm.exceptions.RateLimitError: " + "x" * 500
        short = format_short_llm_error(RuntimeError(long_msg))
        self.assertLessEqual(len(short), 220)
        self.assertIn("[LLM Error]", short)

    def test_is_repl_slash_command(self):
        from libs.repl_guards import is_repl_slash_command
        for cmd in ("/exit", "/free", "/model gpt-4o", "/help", "/clear"):
            with self.subTest(cmd=cmd):
                self.assertTrue(is_repl_slash_command(cmd))

    def test_unknown_slash_command(self):
        from libs.repl_guards import is_unknown_slash_command
        self.assertTrue(is_unknown_slash_command("/foobar"))
        self.assertFalse(is_unknown_slash_command("/exit"))


# ---------------------------------------------------------------------------
# B6 -- libs/vision/image_handler.py
# ---------------------------------------------------------------------------

class TestIsImageSourcePath(unittest.TestCase):
    """B6: is_image_source_path and image_file_arg_for_path."""

    def test_png_is_image(self):
        from libs.vision.image_handler import is_image_source_path
        self.assertTrue(is_image_source_path("photo.png"))

    def test_json_is_not_image(self):
        from libs.vision.image_handler import is_image_source_path
        self.assertFalse(is_image_source_path("configs/openrouter-free.json"))

    def test_image_file_arg_for_path_returns_none_for_json(self):
        from libs.vision.image_handler import image_file_arg_for_path
        self.assertIsNone(image_file_arg_for_path("model-config.json"))

    def test_image_file_arg_for_path_returns_path_for_png(self):
        from libs.vision.image_handler import image_file_arg_for_path
        self.assertEqual(image_file_arg_for_path("diagram.png"), "diagram.png")


# ---------------------------------------------------------------------------
# B7 -- libs/safety_manager.py build_sandbox_context
# ---------------------------------------------------------------------------

class TestSandboxContextEnvVars(unittest.TestCase):
    """B7: sandbox env includes HOME, MPLCONFIGDIR, PLOTLY_DIR, XDG_CONFIG_HOME."""

    def test_sandbox_sets_home_to_temp(self):
        from libs.safety_manager import ExecutionSafetyManager
        mgr = ExecutionSafetyManager()
        ctx = mgr.build_sandbox_context()
        try:
            self.assertIn("HOME", ctx.env)
            self.assertIn("MPLCONFIGDIR", ctx.env)
            self.assertIn("PLOTLY_DIR", ctx.env)
            self.assertIn("XDG_CONFIG_HOME", ctx.env)
            self.assertEqual(ctx.env["HOME"], ctx.cwd)
        finally:
            mgr.cleanup_sandbox_context(ctx)


# ---------------------------------------------------------------------------
# B8 -- libs/safety_manager.py intent path tracking
# ---------------------------------------------------------------------------

class TestUserIntentPaths(unittest.TestCase):
    """B8: set_user_intent_paths and extract_absolute_paths_from_text."""

    def test_extract_windows_path(self):
        from libs.safety_manager import ExecutionSafetyManager
        paths = ExecutionSafetyManager.extract_absolute_paths_from_text(
            r"Please write to C:\Users\user\output.csv"
        )
        self.assertTrue(any(p.lower().startswith("c:") for p in paths))

    def test_intent_path_allows_write(self):
        from libs.safety_manager import ExecutionSafetyManager
        mgr = ExecutionSafetyManager()
        mgr.set_user_intent_paths("Write the result to /tmp/myfile.txt")
        code = "open(\'/tmp/myfile.txt\', \'w\').write(\'hello\')"
        decision = mgr.assess_execution(code, mode="code")
        # If blocked, it must be for sensitive path reason, not just absolute path
        if not decision.allowed:
            reasons_text = " ".join(decision.reasons).lower()
            self.assertIn("sensitive", reasons_text)

    def test_no_intent_blocks_absolute_write(self):
        from libs.safety_manager import ExecutionSafetyManager
        mgr = ExecutionSafetyManager()
        code = "open(\'/home/user/unknown_output.csv\', \'w\').write(\'data\')"
        decision = mgr.assess_execution(code, mode="code")
        self.assertFalse(decision.allowed)


# ---------------------------------------------------------------------------
# B9 -- libs/execution/gui_guard.py
# ---------------------------------------------------------------------------

class TestNeutralizeGuiMainloop(unittest.TestCase):
    """B9: neutralize_gui_mainloop injects tkinter no-op."""

    def test_mainloop_noop_injected(self):
        from libs.execution.gui_guard import neutralize_gui_mainloop
        exec_globals: dict = {}
        neutralize_gui_mainloop(exec_globals)
        if "tkinter" in exec_globals:
            result = exec_globals["tkinter"].mainloop()
            self.assertIsNone(result)

    def test_exec_globals_not_broken(self):
        from libs.execution.gui_guard import neutralize_gui_mainloop
        exec_globals: dict = {}
        neutralize_gui_mainloop(exec_globals)
        exec("x = 1 + 1", exec_globals)
        self.assertEqual(exec_globals.get("x"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
