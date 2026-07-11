import unittest
import os
from unittest.mock import patch, MagicMock
from libs.interpreter_lib import Interpreter

class TestAPIKeysAndModels(unittest.TestCase):
	def setUp(self):
		self.mock_utility_manager = MagicMock()
		self.mock_utility_manager.get_default_model_name.return_value = "gpt-4o"
		self.mock_utility_manager.read_config_file.return_value = {"model": "gpt-4o"}

		self.patcher_um = patch("libs.interpreter_lib.UtilityManager", return_value=self.mock_utility_manager)
		self.patcher_um.start()

		self.patcher_dotenv = patch("libs.interpreter_lib.load_dotenv")
		self.patcher_dotenv.start()

	def tearDown(self):
		patch.stopall()

	def _create_interpreter(self, model_name, provider=""):
		# Mock args — set CLI flags explicitly (MagicMock attrs are truthy).
		args = MagicMock()
		args.model = model_name
		args.mode = "code"
		args.lang = "python"
		args.save_code = False
		args.exec = False
		args.display_code = False
		args.history = False
		args.unsafe = False
		args.sandbox = True
		args.file = None
		args.tui = False
		args.cli = True
		args.agent = False
		args.agentic = False
		args.yes = False
		args.search = False
		args.search_provider = None
		args.search_api_key = None
		args.output_format = "plain"
		args.no_color = False
		args.stream = False
		args.mcp = None
		args.max_context_tokens = 8000
		args.session = None
		args.list_sessions = False
		args.delete_session = None
		args.new_session = False

		# Mock config reading to return the requested model and provider
		self.mock_utility_manager.read_config_file.return_value = {"model": model_name, "provider": provider}

		return Interpreter(args)

	def test_openai_api_key_valid(self):
		with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-12345678"}, clear=True):
			interpreter = self._create_interpreter("gpt-4o")
			self.assertEqual(interpreter.INTERPRETER_MODEL, "gpt-4o")

	def test_openai_api_key_invalid(self):
		with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid-key"}, clear=True):
			with self.assertRaises(Exception) as context:
				self._create_interpreter("gpt-4o")
			self.assertIn("OPENAI_API_KEY should start with 'sk-'", str(context.exception))

	def test_anthropic_api_key_valid(self):
		with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123456"}, clear=True):
			interpreter = self._create_interpreter("claude-3-opus")
			self.assertEqual(interpreter.INTERPRETER_MODEL, "claude-3-opus")

	def test_anthropic_api_key_invalid(self):
		with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-1234"}, clear=True):
			with self.assertRaises(Exception) as context:
				self._create_interpreter("claude-3-opus")
			self.assertIn("ANTHROPIC_API_KEY should start with 'sk-ant-'", str(context.exception))

	def test_gemini_api_key_valid(self):
		with patch.dict(os.environ, {"GEMINI_API_KEY": "1234567890123456"}, clear=True):
			interpreter = self._create_interpreter("gemini-1.5-pro")
			self.assertEqual(interpreter.INTERPRETER_MODEL, "gemini-1.5-pro")

	def test_gemini_api_key_invalid(self):
		with patch.dict(os.environ, {"GEMINI_API_KEY": "short"}, clear=True):
			with self.assertRaises(Exception) as context:
				self._create_interpreter("gemini-1.5-pro")
			self.assertIn("GEMINI_API_KEY should have length greater than 15", str(context.exception))

	def test_groq_api_key_valid(self):
		with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-12345678"}, clear=True):
			interpreter = self._create_interpreter("groq-llama-3")
			self.assertEqual(interpreter.INTERPRETER_MODEL, "groq-llama-3")

	def test_groq_api_key_invalid(self):
		with patch.dict(os.environ, {"GROQ_API_KEY": "invalid"}, clear=True):
			with self.assertRaises(Exception) as context:
				self._create_interpreter("groq-llama-3")
			self.assertIn("GROQ_API_KEY should start with 'gsk'", str(context.exception))

	def test_ollama_local_bypass_api_key(self):
		# Ollama and local models should bypass API key checks.
		# Ensure the environment does not have any keys set.
		with patch.dict(os.environ, {}, clear=True):
			try:
				interpreter = self._create_interpreter("ollama/qwen2.5-coder")
				self.assertEqual(interpreter.INTERPRETER_MODEL, "ollama/qwen2.5-coder")
			except Exception as e:
				self.fail(f"Ollama local model raised an exception unexpectedly: {e}")

	def test_ollama_provider_bypass_api_key(self):
		with patch.dict(os.environ, {}, clear=True):
			try:
				interpreter = self._create_interpreter("mistral-7b", provider="ollama")
				self.assertEqual(interpreter.INTERPRETER_MODEL, "mistral-7b")
			except Exception as e:
				self.fail(f"Ollama local model raised an exception unexpectedly: {e}")

	def test_local_model_bypass_api_key(self):
		with patch.dict(os.environ, {}, clear=True):
			try:
				interpreter = self._create_interpreter("local-model")
				self.assertEqual(interpreter.INTERPRETER_MODEL, "local-model")
			except Exception as e:
				self.fail(f"Local model raised an exception unexpectedly: {e}")

if __name__ == '__main__':
	unittest.main()
