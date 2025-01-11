"""
This is the Code Interpreter class. It provides all methods for Code LLM like Display, Execute, Format code from different llm's.
It includes features like:
- Code execution in multiple languages
- Code extraction from strings
- Saving code to a file
- Executing Code,Scripts
- Checking for compilers
"""

import os
import subprocess
import traceback
from libs.logger import Logger
from libs.markdown_code import display_markdown_message
import tempfile
import logging
import sys

class CodeInterpreter:

	def __init__(self):
		self.logger = logging.getLogger(__name__)
		self.supported_languages = {
			'python': {
				'extension': '.py',
				'compiler': 'python3',
				'version_flag': '--version'
			},
			'javascript': {
				'extension': '.js',
				'compiler': 'node',
				'version_flag': '--version'
			}
		}
	
	def _check_compilers(self, language):
		if language not in self.supported_languages:
			self.logger.error(f"Language {language} not supported")
			raise ValueError(f"Language {language} not supported. Supported languages: {list(self.supported_languages.keys())}")

		compiler_info = self.supported_languages[language]
		try:
			subprocess.run([compiler_info['compiler'], compiler_info['version_flag']], 
						 capture_output=True, check=True)
			return True
		except (subprocess.CalledProcessError, FileNotFoundError):
			self.logger.error(f"Compiler for {language} not found")
			raise RuntimeError(f"Compiler for {language} not found. Please install {compiler_info['compiler']}")

	def execute_code(self, code, language='python'):
		"""Execute code in the specified language."""
		try:
			self._check_compilers(language)
			
			# Create a temporary file with the appropriate extension
			with tempfile.NamedTemporaryFile(suffix=self.supported_languages[language]['extension'], 
										   mode='w', delete=False) as temp_file:
				temp_file.write(code)
				temp_file_path = temp_file.name

			# Execute the code
			compiler = self.supported_languages[language]['compiler']
			process = subprocess.run([compiler, temp_file_path], 
									capture_output=True, 
									text=True)

			# Clean up
			os.unlink(temp_file_path)

			return process.stdout, process.stderr

		except Exception as e:
			self.logger.error(f"Error executing code: {str(e)}")
			return None, str(e)

	def fix_code_errors(self, code, language='python'):
		"""Attempt to fix common code errors."""
		try:
			# Basic syntax fixes
			if language == 'python':
				# Fix indentation
				lines = code.split('\n')
				fixed_lines = []
				current_indent = 0
				
				for line in lines:
					stripped = line.lstrip()
					if stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'try:', 'except:', 'finally:')):
						fixed_lines.append('    ' * current_indent + stripped)
						current_indent += 1
					elif stripped.startswith(('else:', 'elif ')):
						current_indent = max(0, current_indent - 1)
						fixed_lines.append('    ' * current_indent + stripped)
						current_indent += 1
					else:
						fixed_lines.append('    ' * current_indent + stripped)
				
				code = '\n'.join(fixed_lines)
				
				# Add missing colons
				code = code.replace('else\n', 'else:\n')
				code = code.replace('try\n', 'try:\n')
				code = code.replace('except\n', 'except:\n')
				code = code.replace('finally\n', 'finally:\n')
				
			elif language == 'javascript':
				# Add missing semicolons
				lines = code.split('\n')
				fixed_lines = []
				
				for line in lines:
					stripped = line.strip()
					if stripped and not stripped.endswith(';') and \
					   not stripped.endswith('{') and \
					   not stripped.endswith('}') and \
					   not stripped.startswith('//'):
						fixed_lines.append(line + ';')
					else:
						fixed_lines.append(line)
				
				code = '\n'.join(fixed_lines)
				
				# Fix function declarations
				code = code.replace('function(', 'function (')
				
			return code

		except Exception as e:
			self.logger.error(f"Error fixing code: {str(e)}")
			return code

	def extract_code(self, text, start_sep='```', end_sep='```', skip_first_line=True):
		"""Extract code from text between separators."""
		try:
			if not text:
				self.logger.info("No special characters found in the code. Returning the original code.")
				return text

			# Find the first occurrence of start_sep
			start_idx = text.find(start_sep)
			if start_idx == -1:
				self.logger.info("No special characters found in the code. Returning the original code.")
				return text

			# Find the matching end_sep
			end_idx = text.find(end_sep, start_idx + len(start_sep))
			if end_idx == -1:
				self.logger.info("No special characters found in the code. Returning the original code.")
				return text

			# Extract the code between separators
			code = text[start_idx + len(start_sep):end_idx].strip()

			# Skip the first line if it's a language specifier
			if skip_first_line and '\n' in code:
				code = code[code.find('\n')+1:].strip()

			return code

		except Exception as e:
			self.logger.error(f"Error extracting code: {str(e)}")
			return text

	def save_code(self, filename='output/code_generated.py', code=None):
		"""
		Saves the provided code to a file.
		The default filename is 'code_generated.py'.
		"""
		try:
			# Check if the directory exists, if not create it
			directory = os.path.dirname(filename)
			if not os.path.exists(directory):
				os.makedirs(directory)
			
			if not code:
				self.logger.error("Code not provided.")
				display_markdown_message("Error **Code not provided to save.**")
				return

			with open(filename, 'w') as file:
				file.write(code)
				self.logger.info(f"Code saved successfully to {filename}.")
		except Exception as exception:
			self.logger.error(f"Error occurred while saving code to file: {exception}")
			raise Exception(f"Error occurred while saving code to file: {exception}")

	def _execute_script(self, script: str, shell: str):
		stdout = stderr = None
		try:
			if shell == "bash":
				process = subprocess.Popen(['bash', '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			elif shell == "powershell":
				process = subprocess.Popen(['powershell', '-Command', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			elif shell == "applescript":
				process = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			else:
				self.logger.error(f"Invalid shell selected: {shell}")
				return None, f"Invalid shell selected: {shell}"
			stdout, stderr = process.communicate()
			self.logger.info(f"Output is {stdout.decode()} and error is {stderr.decode()}")
			if process.returncode != 0:
				self.logger.error(f"Error in running {shell} script: {stderr.decode()}")
		except Exception as exception:
			self.logger.error(f"Exception in running {shell} script: {str(exception)}")
			stderr = str(exception)
		finally:
			return stdout.decode().strip() if stdout else None, stderr.decode().strip() if stderr else None
		
	def execute_script(self, script:str, os_type:str='macos'):
		output = error = None
		try:
			if not script:
				raise ValueError("Script must be provided.")
			if not os_type:
				raise ValueError("OS type must be provided.")

			self.logger.info(f"Attempting to execute script: {script[:50]}")
			if any(os in os_type.lower() for os in ['darwin', 'macos']):
				output, error = self._execute_script(script, shell='applescript')
			elif 'linux' in os_type.lower():
				output, error = self._execute_script(script, shell='bash')
			elif 'windows' in os_type.lower():
				output, error = self._execute_script(script, shell='powershell')
			else:
				raise ValueError(f"Invalid OS type '{os_type}'. Please provide 'macos', 'linux', or 'windows'.")

			if output:
				self.logger.info(f"Script executed successfully with output: {output[:50]}...")
			if error:
				self.logger.error(f"Script executed with error: {error}...")
		except Exception as exception:
			self.logger.error(f"Error in executing script: {traceback.format_exc()}")
			error = str(exception)
		finally:
			return output, error
		
	def execute_command(self, command:str):
		try:
			if not command:
				raise ValueError("Command must be provided.")
  
			self.logger.info(f"Attempting to execute command: {command}")
			process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

			stdout_output = process.stdout.decode("utf-8")
			stderr_output = process.stderr.decode("utf-8")
  
			if stdout_output:
				self.logger.info(f"Command executed successfully with output: {stdout_output}")
			if stderr_output:
				self.logger.error(f"Command executed with error: {stderr_output}")
  
			return stdout_output, stderr_output
		except Exception as exception:
			self.logger.error(f"Error in executing command: {str(exception)}")
			raise exception
