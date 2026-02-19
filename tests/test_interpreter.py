import unittest
from argparse import Namespace
from unittest.mock import patch

from interpreter import Interpreter


class TestInterpreter(unittest.TestCase):
    def _make_args(self, mode='code', model='code-llama'):
        return Namespace(
            exec=True,
            save_code=True,
            mode=mode,
            model=model,
            display_code=True,
            lang='python',
            file=None,
            history=False,
        )

    @patch('libs.interpreter_lib.Interpreter.initialize_client', return_value=None)
    @patch('libs.utility_manager.UtilityManager.initialize_readline_history', return_value=None)
    def test_mode_is_initialized_from_args(self, _mock_history, _mock_client):
        interpreter = Interpreter(self._make_args(mode='vision', model='gpt-4o'))
        self.assertEqual(interpreter.INTERPRETER_MODE, 'vision')
        self.assertTrue(interpreter.VISION_MODE)
        self.assertFalse(interpreter.CODE_MODE)

    @patch('libs.interpreter_lib.Interpreter.initialize_client', return_value=None)
    @patch('libs.utility_manager.UtilityManager.initialize_readline_history', return_value=None)
    def test_openai_o_series_uses_openai_path(self, _mock_history, _mock_client):
        interpreter = Interpreter(self._make_args(model='o1-mini'))
        interpreter.INTERPRETER_MODEL = 'o1-mini'

        with patch('libs.interpreter_lib.litellm.completion', return_value={'choices': [{'message': {'content': 'ok'}}]}) as completion_mock, \
             patch.object(interpreter.utility_manager, '_extract_content', return_value='ok'):
            response = interpreter.generate_content(
                message='Say hello',
                chat_history=[],
                config_values={'temperature': 0.1, 'max_tokens': 32, 'api_base': 'None'},
            )

        self.assertEqual(response, 'ok')
        completion_mock.assert_called_once()
        self.assertEqual(completion_mock.call_args.args[0], 'o1-mini')

    @patch('libs.interpreter_lib.Interpreter.initialize_client', return_value=None)
    @patch('libs.utility_manager.UtilityManager.initialize_readline_history', return_value=None)
    def test_claude_21_is_not_downgraded_to_claude_2(self, _mock_history, _mock_client):
        interpreter = Interpreter(self._make_args(model='claude-2.1'))
        interpreter.INTERPRETER_MODEL = 'claude-2.1'

        with patch('libs.interpreter_lib.litellm.completion', return_value={'choices': [{'message': {'content': 'ok'}}]}) as completion_mock, \
             patch.object(interpreter.utility_manager, '_extract_content', return_value='ok'):
            interpreter.generate_content(
                message='Ping',
                chat_history=[],
                config_values={'temperature': 0.1, 'max_tokens': 32, 'api_base': 'None'},
            )

        self.assertEqual(completion_mock.call_args.args[0], 'claude-2.1')


if __name__ == '__main__':
    unittest.main()
