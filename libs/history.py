import json
import logging
import os
from typing import List, Any
from libs.logger import Logger

class History:
    def __init__(self, history_file: str):
        self.history_file = history_file
        self.logger = Logger.initialize_logger("logs/interpreter.log")

    def save_history_json(self, task, mode, os_name, language, prompt, code_snippet, code_output, model_name, filename="history/history.json"):
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
                "System": {
                    "Code": code_snippet,
                    "Output": code_output
                }
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

    def get_specific_key(self, key: str) -> List[Any]:
        """Returns a list of all values for the specified key in the history data."""
        try:
            with open(self.history_file, 'r') as file:
                history_data = json.load(file)
            specific_data = []
            for entry in history_data:
                if key in entry['Assistant']:
                    specific_data.append(entry['Assistant'].get(key))
                elif key in entry['System']:
                    specific_data.append(entry['System'].get(key))
            self.logger.info(f'Successfully retrieved {key} data from history')
            return specific_data
        except Exception as exception:
            self.logger.error(f'Error getting {key} data from history: {exception}')
            raise

    def get_last_n_entries(self, count: int) -> List[dict]:
        """Returns the last n entries from the history data."""
        try:
            with open(self.history_file, 'r') as file:
                history_data = json.load(file)
            last_n_entries = history_data[-count:]
            self.logger.info(f'Successfully retrieved last {count} entries from history')
            return last_n_entries
        except Exception as exception:
            self.logger.error(f'Error getting last {count} entries from history: {exception}')
            raise

    def get_last_n_entries_for_key(self, count: int, key: str) -> List[Any]:
        """Returns the values of the specified key for the last n entries in the history data."""
        try:
            last_n_entries = self.get_last_n_entries(count)
            specific_data = self.get_specific_key(key)
            last_n_specific_data = specific_data[-count:]
            self.logger.info(f'Successfully retrieved {key} data for last {count} entries from history')
            return last_n_specific_data
        except Exception as exception:
            self.logger.error(f'Error getting {key} data for last {count} entries from history: {exception}')
            raise