import json
import os
import readline
from libs.logger import initialize_logger


class HelperUtils:
    def __init__(self):
        self.logger = initialize_logger("logs/interpreter.log")

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
            self.logger.error(f"Error in checking OS and version: {str(exception)}")
            raise Exception(f"Error in checking OS and version: {str(exception)}")

    def save_history_json(self, task, mode, os_name, language, prompt, extracted_code, filename="history/history.json"):
        history_entry = {
            "Assistant": {
                "Task": task,
                "Mode": mode,
                "OS": os_name,
                "Language": language
            },
            "User": prompt,
            "System": extracted_code
        }

        if os.path.isfile(filename) and os.path.getsize(filename) > 0:
            with open(filename, "r") as history_file:
                data = json.load(history_file)
        else:
            data = []

        data.append(history_entry)

        with open(filename, "w") as history_file:
            json.dump(data, history_file)

    def initialize_readline_history(self):
        histfile = os.path.join(os.path.expanduser("~"), ".python_history")
        try:
            readline.read_history_file(histfile)
        except FileNotFoundError:
            pass

        import atexit
        atexit.register(readline.write_history_file, histfile)

    def read_config_file(self, filename=".config"):
        try:
            config_data = {}
            with open(filename, "r") as config_file:
                for line in config_file:
                    key, value = line.strip().split("=")
                    config_data[key.strip()] = value.strip()
            return config_data
        except Exception as exception:
            self.logger.error(f"Error in reading config file: {str(exception)}")
            raise Exception(f"Error in reading config file: {str(exception)}")
