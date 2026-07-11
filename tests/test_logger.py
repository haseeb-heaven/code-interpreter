"""Unit tests for Logger level helpers and SafeStreamHandler."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.logger import Logger, SafeStreamHandler


def _reset_logger_singleton():
	logger = Logger._logger
	if logger is not None:
		for handler in list(logger.handlers):
			try:
				handler.close()
			except Exception:
				pass
			logger.removeHandler(handler)
	Logger._logger = None
	Logger._file_handler = None
	Logger._console_handler = None


class TestLoggerLevels(unittest.TestCase):
	def setUp(self):
		_reset_logger_singleton()
		self.tmp = tempfile.TemporaryDirectory()
		self.log_path = str(Path(self.tmp.name) / "test.log")

	def tearDown(self):
		_reset_logger_singleton()
		try:
			self.tmp.cleanup()
		except PermissionError:
			pass

	def test_initialize_and_level_setters(self):
		logger = Logger.initialize(self.log_path)
		self.assertIsInstance(logger, logging.Logger)
		Logger.set_level_to_debug()
		self.assertEqual(Logger.get_current_level(), "DEBUG")
		Logger.set_level_to_info()
		self.assertEqual(Logger.get_current_level(), "INFO")
		Logger.set_level_to_warning()
		self.assertEqual(Logger.get_current_level(), "WARNING")
		Logger.set_level_to_error()
		self.assertEqual(Logger.get_current_level(), "ERROR")
		Logger.set_level_to_critical()
		self.assertEqual(Logger.get_current_level(), "CRITICAL")

	def test_initialize_is_singleton(self):
		a = Logger.initialize(self.log_path)
		b = Logger.initialize(self.log_path)
		self.assertIs(a, b)


class TestSafeStreamHandler(unittest.TestCase):
	def test_unicode_encode_error_is_replaced(self):
		stream = MagicMock()
		handler = SafeStreamHandler(stream)
		handler.setFormatter(logging.Formatter("%(message)s"))
		record = logging.LogRecord(
			name="t", level=logging.ERROR, pathname=__file__, lineno=1,
			msg="café", args=(), exc_info=None,
		)
		with patch.object(
			logging.StreamHandler, "emit", side_effect=UnicodeEncodeError("ascii", "x", 0, 1, "bad")
		):
			handler.emit(record)
		self.assertTrue(stream.write.called)


if __name__ == "__main__":
	unittest.main()
