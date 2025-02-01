import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

class Logger:
	_logger: Optional[logging.Logger] = None
	_file_handler = None
	_console_handler = None

	@staticmethod
	def initialize(filename: str) -> logging.Logger:
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
			Logger._console_handler = logging.StreamHandler()
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
