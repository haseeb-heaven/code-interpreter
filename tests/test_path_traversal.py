import unittest
import os
import tempfile
from unittest.mock import MagicMock
from libs.utility_manager import UtilityManager

class TestPathTraversal(unittest.TestCase):
	def setUp(self):
		self.utility_manager = UtilityManager()
		self.utility_manager.logger = MagicMock()

	def test_get_full_file_path_valid_relative(self):
		cwd = os.getcwd()
		file_name = "test_file.txt"
		expected_path = os.path.abspath(os.path.join(cwd, file_name))
		result = self.utility_manager.get_full_file_path(file_name)
		self.assertEqual(result, expected_path)

	def test_get_full_file_path_path_traversal_relative(self):
		file_name = "../../../etc/passwd"
		result = self.utility_manager.get_full_file_path(file_name)
		self.assertIsNone(result)
		self.utility_manager.logger.warning.assert_called()

	def test_get_full_file_path_path_traversal_absolute(self):
		# Create a temp directory to simulate a path outside of cwd
		with tempfile.TemporaryDirectory() as tmpdirname:
			file_name = os.path.join(tmpdirname, "some_file.txt")
			result = self.utility_manager.get_full_file_path(file_name)
			self.assertIsNone(result)
			self.utility_manager.logger.warning.assert_called()

	def test_get_full_file_path_valid_subfolder(self):
		cwd = os.getcwd()
		file_name = "subfolder/test_file.txt"
		expected_path = os.path.abspath(os.path.join(cwd, file_name))
		result = self.utility_manager.get_full_file_path(file_name)
		self.assertEqual(result, expected_path)

if __name__ == '__main__':
	unittest.main()
