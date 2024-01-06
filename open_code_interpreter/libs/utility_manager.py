import json
import os
import re
from open_code_interpreter.libs.logger import initialize_logger
import traceback
import csv
import pandas as pd
from xml.etree import ElementTree as ET
import glob
from datetime import datetime

from open_code_interpreter.libs.markdown_code import display_code, display_markdown_message

class UtilityManager:
    def __init__(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
        self.logger = initialize_logger("logs/interpreter.log")
        try:
            if not os.path.isfile('logs/interpreter.log'):
                open('logs/interpreter.log', 'w').close()
        except Exception as exception:
            self.logger.error(f"Error in UtilityManager initialization: {str(exception)}")
            raise

    def get_os_platform(self):
        try:
            import platform
            os_info = platform.uname()
            os_name = os_info.system

            os_name_mapping = {
                'Darwin': 'MacOS',
                'Linux': 'Linux',
                'Windows': 'Windows'
            }

            os_name = os_name_mapping.get(os_name, 'Other')

            self.logger.info(f"Operating System: {os_name} Version: {os_info.version}")
            return os_name, os_info.version
        except Exception as exception:
            self.logger.error(f"Error in getting OS platform: {str(exception)}")
            raise

    def save_history_json(self, task, mode, os_name, language, prompt, extracted_code, model_name, filename="history/history.json"):
        try:
            history_entry = {
                "Assistant": {
                    "Task": task,
                    "Mode": mode,
                    "OS": os_name,
                    "Language": language,
                    "Model": model_name
                },
                "User": prompt,
                "System": extracted_code
            }

            data = []
            if os.path.isfile(filename) and os.path.getsize(filename) > 0:
                with open(filename, "r") as history_file:  # Open the file in read mode
                    data = json.load(history_file)

            data.append(history_entry)

            with open(filename, "w") as history_file:
                json.dump(data, history_file)
        except Exception as exception:
            self.logger.error(f"Error in saving history to JSON: {str(exception)}")
            raise

    def initialize_readline_history(self):
        try:
            # Checking the OS type
            # If it's posix (Unix-like), import readline for handling lines from input
            # If it's not posix, import pyreadline as readline
            if os.name == 'posix':
                import readline
            else:
                import pyreadline as readline
                
            histfile = os.path.join(os.path.expanduser("~"), ".python_history")
            readline.read_history_file(histfile)
            
            # Save history to file on exit
            import atexit
            atexit.register(readline.write_history_file, histfile)
        except FileNotFoundError:
            pass
        except Exception as exception:
            self.logger.error(f"Error in initializing readline history: {str(exception)}")
            raise

    def read_config_file(self, filename=".config"):
        try:
            config_data = {}
            with open(filename, "r") as config_file:
                for line in config_file:
                    # Ignore comments and lines without an equals sign
                    if line.strip().startswith('#') or '=' not in line:
                        continue
                    key, value = line.strip().split("=")
                    config_data[key.strip()] = value.strip()
            return config_data
        except Exception as exception:
            self.logger.error(f"Error in reading config file: {str(exception)}")
            raise

    def extract_file_name(self, prompt):
        # This pattern looks for typical file paths, names, and URLs, then stops at the end of the extension
        pattern = r"((?:[a-zA-Z]:\\(?:[\w\-\.]+\\)*|/(?:[\w\-\.]+/)*|\b[\w\-\.]+\b|https?://[\w\-\.]+/[\w\-\.]+/)*[\w\-\.]+\.\w+)"
        match = re.search(pattern, prompt)

        # Return the matched file name or path, if any match found
        if match:
            file_name = match.group()
            file_extension = os.path.splitext(file_name)[1].lower()
            self.logger.info(f"File extension: '{file_extension}'")
            # Check if the file extension is one of the non-binary types
            if file_extension in ['.json', '.csv', '.xml', '.xls', '.txt','.md','.html','.png','.jpg','.jpeg','.gif','.svg','.zip','.tar','.gz','.7z','.rar']:
                self.logger.info(f"Extracted File name: '{file_name}'")
                return file_name
            else:
                return None
        else:
            return None

    def get_full_file_path(self, file_name):
        if not file_name:
            return None

        # Check if the file path is absolute. If not, prepend the current working directory
        if not os.path.isabs(file_name):
            return os.path.join(os.getcwd(), file_name)
        return file_name
    
    def read_csv_headers(self,file_path):
        try:
            with open(file_path, newline='') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader)
                return headers
        except IOError as exception:
            self.logger.error(f"IOError: {exception}")
            return []
        except StopIteration:
            self.logger.error("CSV file is empty.")
            return []

    def get_code_history(self, language='python'):
        try:
            self.logger.info("Starting to read last code history.")
            output_folder = "output"
            file_extension = 'py' if language == 'python' else 'js'
            self.logger.info(f"Looking for files with extension: {file_extension}")

            # Get a list of all files in the output folder with the correct extension
            files = glob.glob(os.path.join(output_folder, f"*.{file_extension}"))
            self.logger.info(f"Found {len(files)} files.")

            # Sort the files by date
            files.sort(key=lambda x: datetime.strptime(x.split('_', 1)[1].rsplit('.', 1)[0], '%Y_%m_%d-%H_%M_%S'), reverse=True)
            self.logger.info("Files sorted by date.")

            # Return the latest file
            latest_file = files[0] if files else None
            self.logger.info(f"Latest file: {latest_file}")

            # Read the file and return the code
            if latest_file:
                with open(latest_file, "r") as code_file:
                    code = code_file.read()
                    return code

        except Exception as exception:
            self.logger.error(f"Error in reading last code history: {str(exception)}")
            raise

    def display_help(self):
        display_markdown_message("Interpreter\n\
                \n\
                Commands available:\n\
                \n\
                /exit - Exit the interpreter.\n\
                /execute - Execute the last code generated.\n\
                /install - Install a package from npm or pip.\n\
                /mode - Change the mode of interpreter.\n\
                /model - Change the model for interpreter.\n\
                /language - Change the language of the interpreter.\n\
                /clear - Clear the screen.\n\
                /help - Display this help message.\n\
                /version - Display the version of the interpreter.\n")
    
    def display_version(self,version):
        display_markdown_message(f"Interpreter - {version}")

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')