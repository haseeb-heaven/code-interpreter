import unittest
import os
from libs.utility_manager import UtilityManager

class TestUtilityManager(unittest.TestCase):
    def setUp(self):
        self.um = UtilityManager()

    def test_get_full_file_path_valid(self):
        # A normal relative path should resolve to absolute within cwd
        path = self.um.get_full_file_path("test.txt")
        self.assertEqual(path, os.path.abspath(os.path.join(os.getcwd(), "test.txt")))

    def test_get_full_file_path_traversal(self):
        # A path trying to traverse up should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.um.get_full_file_path("../../etc/passwd")
        self.assertIn("Path traversal detected", str(context.exception))

    def test_get_full_file_path_absolute(self):
        # An absolute path outside cwd should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.um.get_full_file_path("/etc/passwd")
        self.assertIn("Path traversal detected", str(context.exception))

if __name__ == '__main__':
    unittest.main()
