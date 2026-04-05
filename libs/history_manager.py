import json
import logging
import os
from typing import List, Any
from libs.logger import Logger

class History:
	def __init__(self, history_file: str):
		"""
		Initialize the History instance, set up its logger, and ensure the history file and its parent directory exist (creating them if necessary). If the history file is newly created, write an empty JSON array into it.
		
		Parameters:
			history_file (str): Path to the JSON file used to store history; parent directories will be created if they do not exist.
		"""
		self.history_file = history_file
		self.logger = Logger.initialize("logs/interpreter.log")
		history_dir = os.path.dirname(self.history_file)
		if history_dir and not os.path.exists(history_dir):
			os.makedirs(history_dir, exist_ok=True)
		if not os.path.exists(self.history_file):
			with open(self.history_file, "w", encoding="utf-8") as history_file:
				json.dump([], history_file)

	def save_history_json(self, task, mode, os_name, language, prompt, code_snippet, code_output, model_name):
		"""
		Append a structured history entry to the JSON array stored at the instance's history_file.
		
		Builds an entry containing assistant metadata (`task`, `mode`, `os`, `language`, `model`), the user `prompt`, and system `code` and `output`, then appends it to the JSON array in the history file. If the file does not exist or is empty, a new JSON array is created containing the entry. On failure the error is logged and the original exception is re-raised.
		
		Parameters:
			task (str): High-level task or intent for the assistant.
			mode (str): Mode or context identifier for the session.
			os_name (str): Operating system name or target environment.
			language (str): Programming or natural language associated with the entry.
			prompt (str): User prompt or input text.
			code_snippet (str): Code produced or executed in the session.
			code_output (str): Output or result produced by the code.
			model_name (str): Name of the model used by the assistant.
		"""
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
		"""
		Collects all values associated with a given key from stored history entries.
		
		Parameters:
			key (str): The key to look up within each history entry (searched first in the entry's 'assistant' object, then in 'system').
		
		Returns:
			values (List[Any]): A list of values found for `key` across all history entries. Returns an empty list if the history file is missing, empty, or no entries contain the key.
		"""
		try:
			if not os.path.exists(self.history_file):
				return []
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
		"""
		Retrieve the most recent history entries.
		
		Returns up to `count` of the most recent history records from the history file; returns an empty list if the history file is missing or empty.
		
		Parameters:
			count (int): Maximum number of entries to return. If fewer entries exist, all available entries are returned.
		
		Returns:
			last_entries (List[dict]): A list of history entry dictionaries (up to `count`), ordered from oldest to newest within the returned slice; empty list if no entries are available.
		"""
		try:
			if not os.path.exists(self.history_file) or os.path.getsize(self.history_file) == 0:
				return []
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
		"""
		Assembles up to `count` session dictionaries where each requested key maps to its corresponding most-recent value or `None`.
		
		Parameters:
			count (int): Maximum number of sessions to return.
			*keys (str): One or more history keys to include in each session.
		
		Returns:
			List[dict]: A list of up to `count` dictionaries. Each dictionary maps each requested key to the value at that position in the key's recent-values list or `None` if no value exists for that position. Returns an empty list if none of the requested keys have any entries.
		"""
		last_entries = []
		try:
			entries = {key: self._get_last_entries_for_key(key, count) for key in keys}
			if not any(entries[key] for key in keys):
				return []
			
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
		"""
		Retrieve the most recent code sessions with their corresponding outputs.
		
		Parameters:
			count (int): Maximum number of recent sessions to return.
		
		Returns:
			List[dict]: A list of up to `count` session dictionaries where each dictionary contains the keys `"code"` and `"output"` mapped to their most recent values; missing values are `None`.
		"""
		return self._get_last_entries_for_keys(count, "code", "output")

	def get_full_history(self, count: int) -> List[dict]:
		"""
		Return the most recent sessions containing task, code, and output entries.
		
		Parameters:
			count (int): Maximum number of recent sessions to include.
		
		Returns:
			history (List[dict]): A list with up to `count` session dictionaries. Each session maps the keys `"task"`, `"code"`, and `"output"` to their most recent values (or `None` if a value is missing).
		"""
		return self._get_last_entries_for_keys(count, "task", "code", "output")
