import logging
from logging.handlers import RotatingFileHandler

def initialize_logger(filename):
    # Define the logging format
    log_format = ("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] - %(message)s")
    
    # Create a rotating file handler that will manage log file sizes and backups
    file_handler = RotatingFileHandler(filename, maxBytes=5*1024*1024)  # 5MB per file
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # add logger for console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    # Create the logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Check if the logger already has handlers, if not, add the file handler
    if not logger.handlers:
        logger.addHandler(file_handler)
    
    return logger