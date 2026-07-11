"""End-to-end ReAct workflow test with mocked LLM (no live API)."""
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from libs.agent.react_controller import ReActController


class TestReactEndToEnd(unittest.TestCase):
    def test_full_debug_then_success_path(self):
        """code → execute(fail) → debug → code → execute(ok) → review → finish"""
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "agent_react.jsonl")
            code_interpreter = MagicMock()
            # First execute fails, second succeeds
            code_interpreter.execute_code.side_effect = [
                ("", "NameError: name 'x' is not defined"),
                ("42\n", ""),
            ]
            code_interpreter.extract_code.side_effect = lambda text, *a, **k: (
                "print(x)" if "broken" in text or "print(x)" in text else "print(42)"
            )
            # Simpler: return based on call count inside coder via side_effect on call_llm

            safety = MagicMock()
            safety.build_sandbox_context.return_value = MagicMock()

            controller_steps = [
                (
                    "Thought: write initial code\nAction: code\nAction Input: {\"instruction\": \"broken\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: run it\nAction: execute\nAction Input: {\"language\": \"python\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: debug failure\nAction: debug\nAction Input: {\"error\": \"NameError\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: rewrite\nAction: code\nAction Input: {\"instruction\": \"fixed print 42\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: run again\nAction: execute\nAction Input: {\"language\": \"python\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: review\nAction: review\nAction Input: {}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
                (
                    "Thought: done\nAction: finish\nAction Input: {\"summary\": \"printed 42\"}\n",
                    {"cost": 0.001, "tokens": 5},
                ),
            ]

            coder_responses = [
                ("```python\nprint(x)\n```", {"cost": 0.0, "tokens": 2}),
                ("```python\nprint(42)\n```", {"cost": 0.0, "tokens": 2}),
            ]

            with patch("libs.agent.react_controller.call_llm", side_effect=controller_steps), \
                 patch("libs.agent.actions.coder.call_llm", side_effect=coder_responses), \
                 patch("libs.agent.actions.debugger.call_llm", return_value=("Root cause: NameError. Fix: use 42.", {"cost": 0.0, "tokens": 3})), \
                 patch("libs.agent.actions.reviewer.call_llm", return_value=('{"passed": true, "reason": "prints 42"}', {"cost": 0.0, "tokens": 2})):
                # Use real extract_code behavior via a lightweight stub
                real_extract = MagicMock(side_effect=lambda content, *a, **k: (
                    "print(x)" if "print(x)" in content else "print(42)" if "print(42)" in content else content
                ))
                code_interpreter.extract_code = real_extract

                controller = ReActController(
                    model_name="gpt-4o",
                    api_key="test",
                    code_interpreter=code_interpreter,
                    safety_manager=safety,
                    log_path=log_path,
                    max_steps=12,
                )
                final = controller.run("Print the number 42")

            self.assertEqual(final["status"], "COMPLETED")
            self.assertEqual(final["code"].strip(), "print(42)")
            self.assertTrue(final["review_passed"])
            self.assertEqual(code_interpreter.execute_code.call_count, 2)

            with open(log_path, encoding="utf-8") as fh:
                events = [json.loads(line) for line in fh if line.strip()]
            actions = [e["action"] for e in events if e.get("type") == "step"]
            self.assertEqual(actions, ["code", "execute", "debug", "code", "execute", "review", "finish"])
            summary = [e for e in events if e.get("type") == "summary"][0]
            self.assertEqual(summary["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
