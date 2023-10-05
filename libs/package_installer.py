import subprocess
import re

import logging

class PackageInstaller:
    def __init__(self):
        self.pip_command = "pip"
        self.pip3_command = "pip3"
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] [%(funcName)s] - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def install_package(self, package_name):
        
        if not self.check_package_exists(package_name):
            self.logger.error(f"Package {package_name} does not exist")
            raise ValueError(f"Package {package_name} does not exist")
            
        if not self.is_package_installed(package_name):
            try:
                # Try to install the package using pip
                self.install_package_with_pip(package_name)
            except subprocess.CalledProcessError:
                try:
                    # If pip fails, try to install the package using pip3
                    self.install_package_with_pip3(package_name)
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Failed to install package with both pip and pip3: {package_name}")
                    raise e
        else:
            self.logger.info(f"Package {package_name} is already installed")

    def install_package_with_pip(self, package_name):
        try:
            subprocess.check_call([self.pip_command, "install", package_name])
            self.logger.info(f"Successfully installed package with pip: {package_name}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install package with pip: {package_name}")
            raise e

    def install_package_with_pip3(self, package_name):
        try:
            subprocess.check_call([self.pip3_command, "install", package_name])
            self.logger.info(f"Successfully installed package with pip3: {package_name}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install package with pip3: {package_name}")
            raise e

    def is_package_installed(self, package_name):
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
    
    def extract_package_name(self, error_message):
        # Regular expression pattern to match the error message
        pattern = r"ModuleNotFoundError: No module named '(\w+)'|ModuleNotFoundError: '(\w+)'"
        match = re.search(pattern, error_message)
        if match:
            # Extract the package name from the error message
            package_name = match.group(1) if match.group(1) else match.group(2)
            return package_name
        else:
            # If the package name could not be extracted, log an error and raise an exception
            self.logger.error("Could not extract package name from error message")
            raise ValueError("Could not extract package name from error message")
        
    def check_package_exists(self,package_name):
        import requests
        from bs4 import BeautifulSoup
        
        try:
            # Send a GET request to the PyPI search page
            response = requests.get(f"https://pypi.org/search/?q={package_name}")
            response.raise_for_status()
            
            # Parse the HTML content of the page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search for the package name in the parsed HTML
            search_results = soup.find_all('span', class_='package-snippet__name')
            for result in search_results:
                if result.text.strip() == package_name:
                    return True
            
            # If the package name was not found in the search results, log an error and raise an exception
            raise ValueError(f"Package {package_name} does not exist on PyPI")
        except requests.exceptions.RequestException as e:
            raise e
        

