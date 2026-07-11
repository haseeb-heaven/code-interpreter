"""Unit tests for ReAct JSONL trajectory logger."""
import json
import os
import tempfile
import unittest

from libs.agent.logger import TrajectoryLogger


class TestTrajectoryLogger(unittest.TestCase):
    def test_writes_step_and_summary_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "agent_react.jsonl")
            logger = TrajectoryLogger(path, run_id="run-1")
            logger.log_step(
                step=1,
                thought="write code",
                action="code",
                action_input={"instruction": "hello"},
                observation="print('hi')",
                tokens=10,
                cost=0.01,
                status="running",
            )
            logger.log_summary(status="COMPLETED", steps=1, total_tokens=10, total_cost=0.01)

            with open(path, "r", encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh if line.strip()]

            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["run_id"], "run-1")
            self.assertEqual(lines[0]["action"], "code")
            self.assertEqual(lines[0]["type"], "step")
            self.assertEqual(lines[1]["type"], "summary")
            self.assertEqual(lines[1]["status"], "COMPLETED")

    def test_redacts_api_key_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "agent_react.jsonl")
            logger = TrajectoryLogger(path, run_id="run-2")
            logger.log_step(
                step=1,
                thought="x",
                action="debug",
                action_input={},
                observation="API_KEY=sk-secret-value leaked",
                tokens=0,
                cost=0.0,
                status="running",
            )
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.loads(fh.readline())
            self.assertNotIn("sk-secret-value", payload["observation"])
            self.assertIn("[REDACTED]", payload["observation"])


if __name__ == "__main__":
    unittest.main()
