import logging
from logging.handlers import RotatingFileHandler

class Logger:
	_logger = None

	@staticmethod
	def initialize_logger(filename=None, verbose=False):
		if Logger._logger is None:
			# Define the logging format
			log_format = ("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] - %(message)s")

			# Create a rotating file handler that will manage log file sizes and backups
			file_handler = RotatingFileHandler(filename, maxBytes=5*1024*1024)  # 5MB per file
			file_handler.setFormatter(logging.Formatter(log_format))

			# add logger for console
			console_handler = logging.StreamHandler()
			console_handler.setFormatter(logging.Formatter(log_format))

			# Create the logger
			Logger._logger = logging.getLogger()
			Logger._logger.setLevel(logging.INFO)

			# Check if the logger already has handlers, if not, add the file handler
			if not Logger._logger.handlers:
				Logger._logger.addHandler(file_handler)
				Logger._logger.addHandler(console_handler)

		# Set the logger to verbose or silent mode
		if verbose:
			Logger.set_verbose_mode()
		else:
			Logger.set_silent_mode()

		return Logger._logger

	@staticmethod
	def set_level_to_debug():
		Logger._logger.setLevel(logging.DEBUG)

	@staticmethod
	def set_level_to_info():
		Logger._logger.setLevel(logging.INFO)

	@staticmethod
	def set_level_to_warning():
		Logger._logger.setLevel(logging.WARNING)

	@staticmethod
	def set_level_to_error():
		Logger._logger.setLevel(logging.ERROR)

	@staticmethod
	def set_level_to_critical():
		Logger._logger.setLevel(logging.CRITICAL)
		
	@staticmethod
	def set_verbose_mode():
		Logger._logger.setLevel(logging.DEBUG)

	@staticmethod
	def set_silent_mode():
		Logger._logger.setLevel(logging.ERROR)
		
	@staticmethod
	def get_current_level():
		return logging.getLevelName(Logger._logger.level)