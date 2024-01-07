# test_interpreter.py
import unittest
from interpreter import Interpreter
from argparse import Namespace

class TestInterpreter(unittest.TestCase):
    def test_interpreter_code_mode(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='code-llama', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.mode, 'code')

    def test_interpreter_command_mode(self):
        args = Namespace(exec=True, save_code=True, mode='command', model='gemini-pro', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.mode, 'command')

    def test_interpreter_script_mode(self):
        args = Namespace(exec=True, save_code=True, mode='script', model='mistral-7b', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.mode, 'script')

    def test_interpreter_vision_mode(self):
        args = Namespace(exec=True, save_code=True, mode='vision', model='gpt-3.5-turbo', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.mode, 'vision')

    def test_interpreter_code_llama_model(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='code-llama', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.model, 'code-llama')

    def test_interpreter_gemini_pro_model(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='gemini-pro', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.model, 'gemini-pro')

    def test_interpreter_mistral_7b_model(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='mistral-7b', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.model, 'mistral-7b')

    def test_interpreter_gpt_3_5_turbo_model(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='gpt-3.5-turbo', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.model, 'gpt-3.5-turbo')

    def test_interpreter_gpt_4_model(self):
        args = Namespace(exec=True, save_code=True, mode='code', model='gpt-4', display_code=True, lang='python')
        interpreter = Interpreter(args)
        self.assertEqual(interpreter.args.model, 'gpt-4')

def setup_fake_keys():
    keys = {
        "HUGGINGFACE_API_KEY": "hf_BPubw...",
        "PALM_API_KEY": "AIzaSyDlvk....",
        "GEMINI_API_KEY": "AIzaSyCl...",
        "OPENAI_API_KEY": "sk-ZUZjBz...."
    }

    with open('.env', 'w') as f:
        for key, value in keys.items():
            f.write(f'{key}={value}\n')

if __name__ == '__main__':
    unittest.main()