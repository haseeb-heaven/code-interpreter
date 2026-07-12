"""Unit tests for ReAct controller loop."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from libs.agent.react_controller import ReActController


class TestReactController(unittest.TestCase):
    def _controller(self, log_dir, llm_side_effect):
        code_interpreter = MagicMock()
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()
        safety.cleanup_sandbox_context.return_value = None

        with patch("libs.agent.react_controller.call_llm") as mock_llm, \
             patch("libs.agent.actions.coder.call_llm") as mock_coder_llm, \
             patch("libs.agent.actions.reviewer.call_llm") as mock_reviewer_llm, \
             patch("libs.agent.actions.debugger.call_llm") as mock_debugger_llm:
            # Controller will set these via side effects in each test
            controller = ReActController(
                model_name="gpt-4o",
                api_key="test",
                code_interpreter=code_interpreter,
                safety_manager=safety,
                log_path=os.path.join(log_dir, "agent_react.jsonl"),
                max_steps=5,
            )
            return controller, mock_llm, mock_coder_llm, mock_reviewer_llm, mock_debugger_llm, code_interpreter

    def test_finishes_after_successful_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_interpreter = MagicMock()
            code_interpreter.execute_code.return_value = ("hello\n", "")
            code_interpreter.extract_code.side_effect = lambda text, *a, **k: "print('hello')"
            safety = MagicMock()
            safety.build_sandbox_context.return_value = MagicMock()

            responses = [
                (
                    "Thought: Write code\nAction: code\nAction Input: {\"instruction\": \"print hello\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: Execute\nAction: execute\nAction Input: {\"language\": \"python\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: Review\nAction: review\nAction Input: {}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: Done\nAction: finish\nAction Input: {\"summary\": \"ok\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
            ]

            with patch("libs.agent.react_controller.call_llm", side_effect=responses), \
                 patch("libs.agent.actions.coder.call_llm", return_value=("```python\nprint('hello')\n```", {"cost": 0.0, "tokens": 2})), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": true, "reason": "ok"}', {"cost": 0.0, "tokens": 2})), \
                 patch("libs.agent.actions.debugger.call_llm") as mock_debug:
                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=os.path.join(tmp, "agent_react.jsonl"),
                    max_steps=10,
                )
                final = controller.run("Print hello")

            self.assertEqual(final["status"], "COMPLETED")
            self.assertIn("print", final["code"])
            self.assertGreaterEqual(final["step_count"], 4)
            mock_debug.assert_not_called()
            self.assertTrue(os.path.exists(os.path.join(tmp, "agent_react.jsonl")))

    def test_consecutive_executes_tolerate_odd_language(self):
        """Regression: later execute steps often send prose/empty language."""
        with tempfile.TemporaryDirectory() as tmp:
            code_interpreter = MagicMock()
            code_interpreter.INTERPRETER_LANGUAGE = "python"
            code_interpreter.execute_code.return_value = ("ok\n", "")
            code_interpreter.extract_code.side_effect = lambda text, *a, **k: "print(1)"
            safety = MagicMock()
            safety.build_sandbox_context.return_value = MagicMock()

            responses = [
                (
                    "Thought: write\nAction: code\nAction Input: {\"instruction\": \"print 1\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: run\nAction: execute\nAction Input: {\"language\": \"python\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                # Same-run second execute with prose Action Input (common LLM drift).
                (
                    "Thought: run again\nAction: execute\nAction Input: run it again\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: empty lang\nAction: execute\nAction Input: {\"language\": \"\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: review\nAction: review\nAction Input: {}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: done\nAction: finish\nAction Input: {\"summary\": \"ok\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
            ]

            with patch("libs.agent.react_controller.call_llm", side_effect=responses), \
                 patch("libs.agent.actions.coder.call_llm", return_value=("```python\nprint(1)\n```", {"cost": 0.0, "tokens": 1})), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": true, "reason": "ok"}', {"cost": 0.0, "tokens": 1})):
                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=os.path.join(tmp, "agent_react.jsonl"),
                    max_steps=10,
                )
                final = controller.run("Print 1")

            self.assertEqual(final["status"], "COMPLETED")
            self.assertEqual(code_interpreter.execute_code.call_count, 3)
            for exec_call in code_interpreter.execute_code.call_args_list:
                args, _kwargs = exec_call
                self.assertEqual(args[1], "python")
            observations = [t["observation"] for t in final["trajectory"] if t["action"] == "execute"]
            self.assertTrue(all("ACTION_ERROR" not in o for o in observations))
            self.assertTrue(all("Unsupported language" not in o for o in observations))

    def test_execute_falls_back_to_configured_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_interpreter = MagicMock()
            code_interpreter.INTERPRETER_LANGUAGE = "javascript"
            code_interpreter.execute_code.return_value = ("1\n", "")
            code_interpreter.extract_code.side_effect = lambda text, *a, **k: "console.log(1)"
            safety = MagicMock()
            safety.build_sandbox_context.return_value = MagicMock()

            responses = [
                (
                    "Thought: write\nAction: code\nAction Input: {\"instruction\": \"log 1\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: run\nAction: execute\nAction Input: {\"language\": null}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: review\nAction: review\nAction Input: {}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
                (
                    "Thought: done\nAction: finish\nAction Input: {\"summary\": \"ok\"}\n",
                    {"cost": 0.0, "tokens": 1},
                ),
            ]

            with patch("libs.agent.react_controller.call_llm", side_effect=responses), \
                 patch("libs.agent.actions.coder.call_llm", return_value=("```js\nconsole.log(1)\n```", {"cost": 0.0, "tokens": 1})), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": true, "reason": "ok"}', {"cost": 0.0, "tokens": 1})):
                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=os.path.join(tmp, "agent_react.jsonl"),
                    max_steps=10,
                )
                final = controller.run("Log 1")

            self.assertEqual(final["status"], "COMPLETED")
            self.assertEqual(code_interpreter.execute_code.call_args.args[1], "javascript")

    def test_max_steps_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_interpreter = MagicMock()
            safety = MagicMock()
            responses = [
                (
                    f"Thought: attempt {i}\nAction: review\nAction Input: {{\"attempt\": {i}}}\n",
                    {"cost": 0.0, "tokens": 1},
                )
                for i in range(1, 6)
            ]
            with patch("libs.agent.react_controller.call_llm", side_effect=responses), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": false, "reason": "no"}', {"cost": 0.0, "tokens": 1})):
                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=os.path.join(tmp, "agent_react.jsonl"),
                    max_steps=3,
                )
                final = controller.run("Impossible")

            self.assertEqual(final["status"], "FAILED")
            self.assertEqual(final["step_count"], 3)
            self.assertIn("max_steps", final.get("failure_reason", "").lower())

    def test_stagnation_aborts(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_interpreter = MagicMock()
            safety = MagicMock()
            same = (
                "Thought: again\nAction: review\nAction Input: {}\n",
                {"cost": 0.0, "tokens": 1},
            )
            with patch("libs.agent.react_controller.call_llm", return_value=same), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": false, "reason": "no"}', {"cost": 0.0, "tokens": 1})):
                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=os.path.join(tmp, "agent_react.jsonl"),
                    max_steps=10,
                )
                final = controller.run("stagnate")

            self.assertEqual(final["status"], "FAILED")
            self.assertIn("stagnation", final.get("failure_reason", "").lower())


if __name__ == "__main__":
    unittest.main()
