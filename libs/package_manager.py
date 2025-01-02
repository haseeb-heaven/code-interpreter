import subprocess
import re
import logging
import requests
import stdlib_list
from libs.logger import Logger


class PackageManager:
	logger = None
	
	def __init__(self):
		self.pip_command = "pip"
		self.pip3_command = "pip3"
		self.npm_command = "npm"
		self.logger = Logger.initialize("logs/interpreter.log")

	def install_package(self, package_name, language):
		if language == "python":
			if not self._check_package_exists_pip(package_name):
				exception = ValueError(f"Package {package_name} does not exist")
				self.logger.error(exception)
				raise exception
				
			if not self._is_package_installed(package_name, "pip"):
				try:
					# Try to install the package using pip
					self._install_package_with_pip(package_name)
				except subprocess.CalledProcessError:
					try:
						# If pip fails, try to install the package using pip3
						self._install_package_with_pip3(package_name)
					except subprocess.CalledProcessError as exception:
						self.logger.error(f"Failed to install package with both pip and pip3: {package_name}")
						raise exception
			else:
				self.logger.info(f"Package {package_name} is already installed")
		elif language == "javascript":
			try:
				if not self._check_package_exists_npm(package_name):
					exception = ValueError(f"Package {package_name} does not exist")
					self.logger.error(exception)
					raise exception
			
				if not self._is_package_installed(package_name,"npm"):
					try:
						# Try to install the package using npm
						self._install_package_with_npm(package_name)
					except subprocess.CalledProcessError as exception:
						raise exception
					
			except subprocess.CalledProcessError as exception:
				self.logger.error(f"Failed to install package with npm: {package_name}")
				raise exception
		else:
			exception = ValueError("Invalid language selected.")
			self.logger.error(exception)
			raise exception
		
	def extract_package_name(self, error,language):
		if language == "python":
			return self._extract_python_package_name(error)
		elif language == "javascript":
			return self._extract_javascript_package_name(error)
		else:
			exception = ValueError("Invalid language selected.")
			self.logger.error(exception)
			raise exception

	def get_system_modules(self):
		try:
			# Get a list of all module names in the standard library
			stdlib = stdlib_list.stdlib_list()
			return stdlib
		except Exception as exception:
			raise ValueError("An error occurred while getting module names") from exception
	
	def _install_package_with_pip(self,  package_name):
		try:
			subprocess.check_call([self.pip_command, "install", package_name])
			self.logger.info(f"Successfully installed package with pip: {package_name}")
		except subprocess.CalledProcessError as exception:
			self.logger.error(f"Failed to install package with pip: {package_name}")
			raise exception

	def _install_package_with_pip3(self,  package_name):
		try:
			subprocess.check_call([self.pip3_command, "install", package_name])
			self.logger.info(f"Successfully installed package with pip3: {package_name}")
		except subprocess.CalledProcessError as exception:
			self.logger.error(f"Failed to install package with pip3: {package_name}")
			raise exception
		
	def _install_package_with_npm(self,  package_name):
		try:
			subprocess.check_call([self.npm_command, "install", package_name])
			self.logger.info(f"Successfully installed package with npm: {package_name}")
		except subprocess.CalledProcessError as exception:
			self.logger.error(f"Failed to install package with npm: {package_name}")
			raise exception
		
	def _is_package_installed(self,  package_name, package_manager):
		if package_manager == "pip":
			try:
				subprocess.check_call([self.pip_command, "show", package_name])
				self.logger.info(f"Package {package_name} is installed")
				return True
			except subprocess.CalledProcessError:
				try:
					subprocess.check_call([self.pip3_command, "show", package_name])
					self.logger.info(f"Package {package_name} is installed")
					return True
				except subprocess.CalledProcessError:
					self.logger.info(f"Package {package_name} is not installed")
					return False
		elif package_manager == "npm":
			try:
				subprocess.check_call([self.npm_command, "list", "-g", package_name])
				self.logger.info(f"Package {package_name} is installed")
				return True
			except subprocess.CalledProcessError:
				self.logger.info(f"Package {package_name} is not installed")
				return False
		else:
			exception = ValueError("Invalid package manager selected.")
			self.logger.error(exception)
			raise exception

	def _extract_python_package_name(self,  error_message):
		# Regular expression pattern to match the error message
		pattern = r"ModuleNotFoundError: No module named '(\w+)'|ModuleNotFoundError: '(\w+)'"
		match = re.search(pattern, error_message)
		if match:
			# Extract the package name from the error message
			package_name = match.group(1) if match.group(1) else match.group(2)
			return package_name
		else:
			# If the package name could not be extracted, log an error and raise an exception
			exception = ValueError("Could not extract package name from error message")
			self.logger.error(exception)
			raise exception
	
	def _extract_javascript_package_name(self, error_message):
		try:
			lines = error_message.split('\n')
			for line in lines:
				if line.startswith("Error: Cannot find module"):
					package_name = line.split("'")[1]
					return package_name
			return None
		except Exception as exception:
			self.logger.error(f"Failed to extract package name from error message: {exception}")
			raise exception
		
	def _check_package_exists_pip(self, package_name):
		try:
			api_url = f"https://pypi.org/pypi/{package_name}/json"
			self.logger.info("API Url is {}".format(api_url))
			response = requests.get(api_url)
			if response.status_code == 200:
				return True
			else:
				error_message = f"Package {package_name} does not exist on PyPI"
				self.logger.error(error_message)
				raise ValueError(error_message)
		except requests.exceptions.RequestException as request_exception:
			self.logger.error(f"Request failed: {request_exception}")
			raise request_exception
		
	def _check_package_exists_npm(self,  package_name):
		try:
			response = requests.get(f"https://www.npmjs.com/package/{package_name}")
			if response.status_code == 200:
				self.logger.info(f"Package {package_name} exists on npm website")
				return True
			else:
				self.logger.info(f"Package {package_name} does not exist on npm website")
				return False
		except requests.exceptions.RequestException as exception:
			self.logger.error(f"Failed to check package existence on npm website: {exception}")
			raise exception
