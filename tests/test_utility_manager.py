import unittest
import os
from libs.utility_manager import UtilityManager

class TestUtilityManager(unittest.TestCase):
	def setUp(self):
		self.manager = UtilityManager()

	def test_get_full_file_path_valid(self):
		valid_path = "valid_file.txt"
		expected_path = os.path.abspath(os.path.join(os.getcwd(), valid_path))
		self.assertEqual(self.manager.get_full_file_path(valid_path), expected_path)

		# test absolute path inside cwd
		self.assertEqual(self.manager.get_full_file_path(expected_path), expected_path)

	def test_get_full_file_path_traversal(self):
		# Test relative path traversal
		with self.assertRaises(ValueError) as context:
			self.manager.get_full_file_path('../etc/passwd')
		self.assertIn("Security Error: Path traversal attempt detected", str(context.exception))

		# Test absolute path outside cwd
		with self.assertRaises(ValueError) as context:
			self.manager.get_full_file_path('/etc/passwd')
		self.assertIn("Security Error: Path traversal attempt detected", str(context.exception))

if __name__ == '__main__':
	unittest.main()
