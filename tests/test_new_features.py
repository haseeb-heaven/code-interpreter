import unittest
from unittest.mock import patch, MagicMock
import platform
import os
import sys

from libs.utility_manager import UtilityManager
from libs.package_manager import PackageManager
from libs.terminal_ui import TerminalUI
from libs.safety_manager import ExecutionSafetyManager
import requests

class TestNewFeatures(unittest.TestCase):
    @patch('platform.system')
    @patch('os.path.isfile')
    @patch('os.startfile', create=True)
    def test_utility_manager_open_resource_file_windows(self, mock_startfile, mock_isfile, mock_system):
        mock_system.return_value = 'Windows'
        mock_isfile.return_value = True
        
        um = UtilityManager()
        um._open_resource_file('test.txt')
        
        mock_startfile.assert_called_once_with('test.txt')

    @patch('requests.get')
    def test_package_manager_pypi_timeout(self, mock_get):
        mock_get.return_value.status_code = 200
        pm = PackageManager()
        pm._check_package_exists_pip('requests')
        mock_get.assert_called_once_with('https://pypi.org/pypi/requests/json', timeout=10)

    @patch('requests.get')
    def test_package_manager_npm_timeout(self, mock_get):
        mock_get.return_value.status_code = 200
        pm = PackageManager()
        pm._check_package_exists_npm('express')
        mock_get.assert_called_once_with('https://registry.npmjs.org/express', timeout=10)

    @patch('requests.get')
    def test_utility_manager_requests_timeout(self, mock_get):
        mock_get.return_value.status_code = 200
        with patch('builtins.open', unittest.mock.mock_open()):
            UtilityManager._download_file('http://example.com/test.txt', 'test.txt')
        mock_get.assert_called_once_with('http://example.com/test.txt', allow_redirects=True, timeout=10)

    @patch('sys.stdin.isatty', return_value=False)
    @patch('libs.terminal_ui.Prompt.ask')
    def test_terminal_ui_prompt_choices(self, mock_ask, mock_isatty):
        mock_ask.return_value = 'yes'
        ui = TerminalUI()
        ui._select_option("Mode", ["yes", "no"], "yes")
        args, kwargs = mock_ask.call_args
        self.assertIn("[yes|no]", args[0])

    def test_safety_manager_precompiled_regexes(self):
        sm = ExecutionSafetyManager()
        self.assertTrue(isinstance(sm._WRITE_PATTERNS_COMPILED, tuple))
        self.assertTrue(isinstance(sm._DESTRUCTIVE_PATTERNS_COMPILED, tuple))

if __name__ == '__main__':
    unittest.main()
