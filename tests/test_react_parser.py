"""Unit tests for ReAct Thought/Action/Action Input parser."""
import unittest

from libs.agent.parser import ParseError, parse_react_step


class TestReactParser(unittest.TestCase):
    def test_parses_thought_action_and_input(self):
        text = (
            "Thought: I should write code first.\n"
            "Action: code\n"
            'Action Input: {"instruction": "print hello"}\n'
        )
        step = parse_react_step(text)
        self.assertEqual(step.thought, "I should write code first.")
        self.assertEqual(step.action, "code")
        self.assertEqual(step.action_input, {"instruction": "print hello"})

    def test_parses_free_text_action_input(self):
        text = (
            "Thought: Run it.\n"
            "Action: execute\n"
            "Action Input: python\n"
        )
        step = parse_react_step(text)
        self.assertEqual(step.action, "execute")
        self.assertEqual(step.action_input, "python")

    def test_parses_finish_action(self):
        text = (
            "Thought: Done.\n"
            "Action: finish\n"
            'Action Input: {"summary": "Task complete"}\n'
        )
        step = parse_react_step(text)
        self.assertEqual(step.action, "finish")
        self.assertEqual(step.action_input["summary"], "Task complete")

    def test_case_insensitive_action_name(self):
        text = "Thought: x\nAction: Review\nAction Input: {}\n"
        step = parse_react_step(text)
        self.assertEqual(step.action, "review")

    def test_raises_on_missing_action(self):
        with self.assertRaises(ParseError):
            parse_react_step("Thought: only thinking\n")

    def test_raises_on_empty_text(self):
        with self.assertRaises(ParseError):
            parse_react_step("")

    def test_ignores_trailing_observation_in_model_output(self):
        text = (
            "Thought: check\n"
            "Action: review\n"
            "Action Input: {}\n"
            "Observation: should be ignored\n"
        )
        step = parse_react_step(text)
        self.assertEqual(step.action, "review")
        self.assertIsNone(step.observation)


if __name__ == "__main__":
    unittest.main()
