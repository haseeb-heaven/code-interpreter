import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

logging.raiseExceptions = False


class SafeStreamHandler(logging.StreamHandler):
	"""A console handler that degrades non-encodable characters safely on Windows."""

	def emit(self, record):
		"""
		Emit a log record to the handler's stream, falling back to an ASCII-safe representation on encoding errors.
		
		Attempts to emit the provided logging record normally. If a UnicodeEncodeError occurs while writing to the stream, formats the record and writes an ASCII-safe version (with replacement characters) to the stream, then flushes. If the fallback write fails, delegates error handling to the handler's error handler.
		
		Parameters:
			record (logging.LogRecord): The log record to be emitted.
		"""
		try:
			super().emit(record)
		except UnicodeEncodeError:
			try:
				msg = self.format(record)
				safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
				self.stream.write(safe_msg + self.terminator)
				self.flush()
			except Exception:
				self.handleError(record)


class Logger:
	_logger: Optional[logging.Logger] = None
	_file_handler = None
	_console_handler = None

	@staticmethod
	def initialize(filename: str) -> logging.Logger:
		"""
		Initialize and return a singleton logger configured with a rotating file handler and a console handler.
		
		Parameters:
			filename (str): Path (and logger name) for the rotating log file. If a logger for this name already exists, the existing configured logger is returned.
		
		Returns:
			logging.Logger: The singleton logger configured with a rotating file handler (5MB max per file, 5 backups) and a console stream handler.
		"""
		if Logger._logger is None:
			Logger._logger = logging.getLogger(filename)
			Logger._logger.setLevel(logging.DEBUG)

			# Ensure no debug prints on console from any library
			Logger._logger.propagate = False

			# Define the logging format
			log_format = ("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] - %(message)s")

			# Create a rotating file handler to manage log file sizes and backups
			Logger._file_handler = RotatingFileHandler(filename, maxBytes=5*1024*1024, backupCount=5)  # 5MB per file
			Logger._file_handler.setFormatter(logging.Formatter(log_format))
			Logger._file_handler.setLevel(logging.DEBUG)

			# Create a console handler
			Logger._console_handler = SafeStreamHandler()
			Logger._console_handler.setFormatter(logging.Formatter(log_format))
			Logger._console_handler.setLevel(logging.ERROR)

			# Filter out debug logs from console
			Logger._console_handler.addFilter(lambda record: record.levelno >= logging.INFO)

			# Add handlers to the logger
			Logger._logger.addHandler(Logger._file_handler)
			Logger._logger.addHandler(Logger._console_handler)

		return Logger._logger

	@staticmethod
	def set_level_to_info():
		if Logger._file_handler:
			Logger._file_handler.setLevel(logging.DEBUG)  # Keep file at DEBUG
		if Logger._console_handler:
			Logger._console_handler.setLevel(logging.INFO)

	@staticmethod
	def set_level_to_debug():
		if Logger._file_handler:
			Logger._file_handler.setLevel(logging.DEBUG)  # Keep file at DEBUG
		if Logger._console_handler:
			Logger._console_handler.setLevel(logging.DEBUG)

	@staticmethod
	def set_level_to_warning():
		if Logger._file_handler:
			Logger._file_handler.setLevel(logging.DEBUG)  # Keep file at DEBUG
		if Logger._console_handler:
			Logger._console_handler.setLevel(logging.WARNING)

	@staticmethod
	def set_level_to_error():
		if Logger._file_handler:
			Logger._file_handler.setLevel(logging.DEBUG)  # Keep file at DEBUG
		if Logger._console_handler:
			Logger._console_handler.setLevel(logging.ERROR)

	@staticmethod
	def set_level_to_critical():
		if Logger._file_handler:
			Logger._file_handler.setLevel(logging.DEBUG)  # Keep file at DEBUG
		if Logger._console_handler:
			Logger._console_handler.setLevel(logging.CRITICAL)
		
	@staticmethod
	def get_current_level():
		if Logger._console_handler:
			return logging.getLevelName(Logger._console_handler.level)
		return logging.getLevelName(logging.NOTSET)
