import json
import logging
import os
from typing import List, Any
from libs.logger import Logger

class History:
	def __init__(self, history_file: str):
		self.history_file = history_file
		self.logger = Logger.initialize("logs/interpreter.log")

	def save_history_json(self, task, mode, os_name, language, prompt, code_snippet, code_output, model_name):
		try:
			history_entry = {
				"assistant": {
					"task": task,
					"mode": mode,
					"os": os_name,
					"language": language,
					"model": model_name
				},
				"user": prompt,
				"system": {
					"code": code_snippet,
					"output": code_output
				}
			}

			data = []
			if os.path.isfile(self.history_file) and os.path.getsize(self.history_file) > 0:
				with open(self.history_file, "r") as history_file:  # Open the file in read mode
					data = json.load(history_file)

			data.append(history_entry)

			with open(self.history_file, "w") as history_file:
				json.dump(data, history_file)
		except Exception as exception:
			self.logger.error(f"Error in saving history to JSON: {str(exception)}")
			raise

	def _get_data_for_key(self, key: str) -> List[Any]:
		"""Returns a list of all values for the specified key in the history data."""
		try:
			if os.path.getsize(self.history_file) > 0:
				with open(self.history_file, 'r') as file:
					history_data = json.load(file)
			else:
				return []
			
			specific_data = []
			for entry in history_data:
				if key in entry['assistant']:
					specific_data.append(entry['assistant'].get(key))
				elif key in entry['system']:
					specific_data.append(entry['system'].get(key))
			self.logger.info(f'Successfully retrieved {key} data from history')
			return specific_data
		except Exception as exception:
			self.logger.error(f'Error getting {key} data from history: {exception}')
			raise

	def _get_last_entries(self, count: int) -> List[dict]:
		"""Returns the last n entries from the history data."""
		try:
			with open(self.history_file, 'r') as file:
				history_data = json.load(file)
			last_entries = history_data[-count:]
			self.logger.info(f'Successfully retrieved last {count} entries from history')
			return last_entries
		except Exception as exception:
			self.logger.error(f'Error getting last {count} entries from history: {exception}')
			raise

	def _get_last_entries_for_key(self, key: str, count: int) -> List[Any]:
		"""Returns the values of the specified key for the last n entries in the history data."""
		try:
			specific_key_data = self._get_data_for_key(key)
			last_specific_data = specific_key_data[-count:]
			if last_specific_data:
				self.logger.info(f'Successfully retrieved {key} data for last {count} entries from history')
				self.logger.info(f"\n'{last_specific_data}'\n")
				return last_specific_data
			else:
				self.logger.info(f'No {key} data found in history')
				return []
		except Exception as exception:
			self.logger.error(f'Error getting {key} data for last {count} entries from history: {exception}')
			raise
		
	def _get_last_entries_for_keys(self, count: int, *keys: str) -> List[dict]:
		last_entries = []
		try:
			entries = {key: self._get_last_entries_for_key(key, count) for key in keys}
			
			for index in range(count):
				session = {key: entries[key][index] if index < len(entries[key]) else None for key in keys}
				last_entries.append(session)
			
			return last_entries
		except Exception as exception:
			self.logger.error(f'Error getting last {count} entries for keys {keys} from history: {exception}')
			raise

	def get_chat_history(self, count: int) -> List[dict]:
		return self._get_last_entries_for_keys(count, "task", "output")

	def get_code_history(self, count: int) -> List[dict]:
		return self._get_last_entries_for_keys(count, "code", "output")

	def get_full_history(self, count: int) -> List[dict]:
		return self._get_last_entries_for_keys(count, "task", "code", "output")