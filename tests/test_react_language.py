"""Unit tests for ReAct execute language resolution."""
import unittest

from libs.agent.language import (
    normalize_execute_language,
    resolve_react_execute_language,
)


class _Interp:
    def __init__(self, language="python"):
        self.INTERPRETER_LANGUAGE = language


class TestNormalizeExecuteLanguage(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_execute_language("py"), "python")
        self.assertEqual(normalize_execute_language("Python3"), "python")
        self.assertEqual(normalize_execute_language("js"), "javascript")
        self.assertEqual(normalize_execute_language("node"), "javascript")

    def test_empty_and_odd(self):
        self.assertIsNone(normalize_execute_language(""))
        self.assertIsNone(normalize_execute_language(None))
        self.assertIsNone(normalize_execute_language("none"))
        self.assertIsNone(normalize_execute_language("run it again"))
        self.assertIsNone(normalize_execute_language("ruby"))


class TestResolveReactExecuteLanguage(unittest.TestCase):
    def test_missing_key_uses_default(self):
        self.assertEqual(resolve_react_execute_language({}, _Interp("python")), "python")

    def test_empty_and_null_fall_back(self):
        self.assertEqual(
            resolve_react_execute_language({"language": ""}, _Interp("python")),
            "python",
        )
        self.assertEqual(
            resolve_react_execute_language({"language": None}, _Interp("javascript")),
            "javascript",
        )

    def test_prose_string_falls_back(self):
        self.assertEqual(
            resolve_react_execute_language("run it again", _Interp("python")),
            "python",
        )

    def test_valid_and_alias(self):
        self.assertEqual(
            resolve_react_execute_language({"language": "python"}, _Interp()),
            "python",
        )
        self.assertEqual(
            resolve_react_execute_language({"language": "py"}, _Interp()),
            "python",
        )
        self.assertEqual(
            resolve_react_execute_language("javascript", _Interp("python")),
            "javascript",
        )

    def test_unknown_token_falls_back_for_react(self):
        # ReAct should not abort the loop on LLM-invented languages.
        self.assertEqual(
            resolve_react_execute_language({"language": "ruby"}, _Interp("python")),
            "python",
        )


if __name__ == "__main__":
    unittest.main()
