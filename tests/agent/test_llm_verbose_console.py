# -*- coding: utf-8 -*-
"""Unit tests for the retry/fallback chatter verbosity toggle in ``libs.agent.llm``.

The noisy "Rate limited; sleeping…" / "Retrying … after rate limit…" /
"Free model fallback succeeded…" / "Model called a tool unexpectedly…" lines
are pure step-level noise in the default --agentic Thought-only view. They are
logged via ``_chatter``, which is silent (DEBUG) by default and only escalates
to console-visible WARNING when ``set_verbose_console(True)`` has been called
(wired to ``--verbose``/``-V``/``/verbose`` via ``ReActController``).
"""
from __future__ import annotations

import logging
import unittest

from libs.agent import llm as llm_module


class VerboseConsoleToggleTests(unittest.TestCase):
    def tearDown(self):
        llm_module.set_verbose_console(False)

    def test_defaults_to_non_verbose(self):
        llm_module.set_verbose_console(False)
        self.assertFalse(llm_module.is_verbose_console())

    def test_chatter_logs_at_debug_when_not_verbose(self):
        llm_module.set_verbose_console(False)
        with self.assertLogs("libs.agent.llm", level="DEBUG") as ctx:
            llm_module._chatter("Rate limited; sleeping %.1fs before retry…", 2.0)
        levels = {record.levelno for record in ctx.records}
        self.assertEqual(levels, {logging.DEBUG})

    def test_chatter_escalates_to_warning_when_verbose(self):
        llm_module.set_verbose_console(True)
        self.assertTrue(llm_module.is_verbose_console())
        with self.assertLogs("libs.agent.llm", level="DEBUG") as ctx:
            llm_module._chatter(
                "Retrying %s after rate limit (%s/%s)…", "groq/llama-3.1-8b-instant", 1, 2
            )
        levels = {record.levelno for record in ctx.records}
        self.assertEqual(levels, {logging.WARNING})

    def test_genuine_errors_stay_at_error_level_regardless_of_verbose(self):
        """``_chatter`` only governs retry/fallback noise; unrecoverable
        failures (e.g. the final exhaustion message) must always log at
        ERROR, unaffected by the console-verbosity toggle."""
        llm_module.set_verbose_console(False)
        with self.assertLogs("libs.agent.llm", level="DEBUG") as ctx:
            llm_module.logger.error("LLM call failed: %s", "boom")
        levels = {record.levelno for record in ctx.records}
        self.assertEqual(levels, {logging.ERROR})


if __name__ == "__main__":
    unittest.main()
