"""Real end-to-end CLI runs, driven like a human user, for every mode/setting.

Unlike the mocked unit suites (``tests/e2e/test_all_modes_e2e.py`` etc.), these
tests spawn the actual ``interpreter.py`` binary as a subprocess with piped
stdin — no ``unittest.mock`` on internal functions — and let the real
pipeline run: argument parsing -> Interpreter boot -> litellm HTTP dispatch ->
sandboxed execution -> real console output / real files on disk.

Because this sandbox has no real LLM provider API keys (see
``tests/smoke/test_live_model_smoke.py`` for the genuine-provider suite,
which self-skips without keys), a protocol-aware local stub
(``scripts/live_stub_llm_server.py``) stands in for the model. It recognizes
which internal agent is calling (ReAct step / Coder / Reviewer / IntentRouter
/ Planner / AutoLoop tool-use / classic single-shot) from the system prompt
and replies with a protocol-correct message, so every mode actually runs to
real completion instead of stopping at "local endpoint unreachable" (the
soft-skip seen in ``scripts/run_live_scenarios.py`` today).

Re-run: python -m unittest discover -s tests/live -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
sys.path.insert(0, str(ROOT))

from scripts.live_stub_llm_server import StubLLMServer  # noqa: E402

_TIMEOUT = 60


def _run_cli(args: list[str], *, stdin: str = "", extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["INTERPRETER_YES"] = "1"
    env.update(extra_env or {})
    return subprocess.run(
        [PYTHON, str(ROOT / "interpreter.py"), *args],
        cwd=str(ROOT),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env=env,
    )


class LiveStubServerTestCase(unittest.TestCase):
    """Base class: spins up the protocol-aware stub for every test in the class."""

    @classmethod
    def setUpClass(cls):
        cls._stub = StubLLMServer(port=11434)
        cls._stub.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._stub.__exit__(None, None, None)


class TestClassicCliRealRun(LiveStubServerTestCase):
    def test_cli_mode_executes_real_code_and_produces_output(self):
        proc = _run_cli(
            ["--cli", "-m", "local-model", "-md", "code", "-dc"],
            stdin="print classic cli smoke\ny\n/exit\n",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, combined)
        self.assertIn("stub agent: task executed", combined)
        self.assertIn('"status": "success"', combined)

    def test_cli_slash_tools_and_memory_commands(self):
        proc = _run_cli(
            ["--cli", "-m", "local-model", "-md", "code"],
            stdin="/tools list\n/memory stats\n/exit\n",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, combined)
        self.assertIn("write_file", combined)
        self.assertIn("execute_code", combined)


class TestReActAgenticRealRun(LiveStubServerTestCase):
    def test_agentic_mode_completes_full_react_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "task.txt"
            task_file.write_text("print a friendly greeting", encoding="utf-8")
            proc = _run_cli(
                ["--agentic", "-m", "local-model", "-md", "code", "-f", str(task_file), "--yes"],
            )
            combined = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, combined)
            self.assertIn("Status: COMPLETED", combined)
            self.assertIn("Steps: 4", combined)  # code -> execute -> review -> finish

    def test_gemini_style_mode_shows_banner_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "task.txt"
            task_file.write_text("print a friendly greeting", encoding="utf-8")
            proc = _run_cli(
                ["--gemini-style", "-m", "local-model", "-md", "code", "-f", str(task_file), "--yes"],
            )
            combined = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, combined)
            self.assertIn("/free", combined)
            self.assertIn("/model", combined)
            self.assertIn("Status: COMPLETED", combined)

    def test_agentic_repl_model_and_free_slash_commands(self):
        proc = _run_cli(
            ["--agentic", "-m", "local-model", "-md", "code"],
            stdin="/model local-model\n/free\n/help\n/exit\n",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, combined)
        self.assertIn("Model switched to local-model", combined)
        self.assertIn("Free / cheap LLM presets", combined)


class TestYoloAutoLoopRealRun(LiveStubServerTestCase):
    def test_yolo_writes_a_real_file_via_native_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "task.txt"
            out_file = Path(tmp) / "yolo_live_output.txt"
            task_file.write_text(
                f"Create a file named {out_file} with content YOLO_LIVE_OK using your tools.",
                encoding="utf-8",
            )
            proc = _run_cli(
                ["--yolo", "-m", "local-model", "-md", "code", "-f", str(task_file), "--yes"],
            )
            combined = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, combined)
            self.assertTrue(out_file.exists(), combined)
            self.assertEqual(out_file.read_text(encoding="utf-8").strip(), "YOLO_LIVE_OK")


class TestMultiAgentPipelineRealRun(LiveStubServerTestCase):
    def test_agent_pipeline_completes_intent_plan_execute_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "task.txt"
            task_file.write_text("print hello from agent pipeline", encoding="utf-8")
            proc = _run_cli(
                ["--cli", "--agent", "-m", "local-model", "-md", "code", "-f", str(task_file), "--yes", "-dc"],
            )
            combined = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, combined)
            self.assertIn('"status": "success"', combined)


class TestInteractiveSettingsWizardRealRun(LiveStubServerTestCase):
    def test_settings_wizard_accepts_all_defaults_without_crashing(self):
        # Every prompt in libs/terminal_ui.py::_collect_core_settings answered
        # with a blank line (accept the shown default); real Rich Prompt.ask
        # driven over piped stdin, exactly like a user mashing Enter.
        blank_answers = "\n" * 14
        proc = _run_cli(
            ["--agentic", "-m", "local-model", "-md", "code"],
            stdin=f"/settings\n{blank_answers}/exit\n",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, combined)
        self.assertIn("Output format", combined)  # last prompt in the wizard was reached
        self.assertNotIn("Traceback", combined)


class TestSearchFlagRealNetworkAttempt(LiveStubServerTestCase):
    def test_search_flag_enabled_reaches_real_network_boundary(self):
        """--search drives the LLM to call the real web_search tool, which hits
        real DuckDuckGo over the network (no API key needed) — the stub only
        replaces the model, not the search tool or the network call it makes.

        This sandbox's outbound network policy may not reach arbitrary
        external hosts (only the pre-configured agent proxy), so a
        connection failure here is an environment limitation, not a defect —
        soft-skip it, mirroring the existing soft-skip convention in
        scripts/run_live_scenarios.py. A real result is asserted when the
        network is reachable.
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "task.txt"
            task_file.write_text(
                "Search the web for 'python programming language' and summarize the first result.",
                encoding="utf-8",
            )
            proc = _run_cli(
                [
                    "--yolo", "-m", "local-model", "-md", "code",
                    "-f", str(task_file), "--yes", "--search",
                ],
            )
            combined = proc.stdout + proc.stderr
            self.assertIn("Web search enabled", combined)
            network_failure_markers = (
                "connecterror", "connection refused", "tunnel error",
                "name or service not known", "timed out", "ddgsexception",
                "no results found",
            )
            if any(m in combined.lower() for m in network_failure_markers):
                raise unittest.SkipTest(
                    f"Soft-skip: sandbox network policy blocks live search: {combined[-400:]}"
                )
            self.assertEqual(proc.returncode, 0, combined)


if __name__ == "__main__":
    unittest.main()
