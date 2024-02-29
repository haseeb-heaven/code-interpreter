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
import re
import subprocess
import tempfile
import traceback
from libs.logger import Logger
from libs.markdown_code import display_markdown_message

class CodeInterpreter:

    def __init__(self):
        self.logger = Logger.initialize_logger("logs/code-interpreter.log")
    
    def _execute_script(self, script: str, shell: str):
        stdout = stderr = None
        try:
            self.logger.info(f"Running {shell} script")
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
        
    def _check_compilers(self, language):
        try:
            language = language.lower().strip()
            
            compilers = {
                "python": ["python", "--version"],
                "javascript": ["node", "--version"],
                "cpp": ["g++", "--version"],
                "java": ["javac", "--version"],
            }

            if language not in compilers:
                self.logger.error("Invalid language selected.")
                return False

            compiler = subprocess.run(compilers[language], capture_output=True, text=True)
            if compiler.returncode != 0:
                self.logger.error(f"{language.capitalize()} compiler not found.")
                return False

            return True
        except Exception as exception:
            self.logger.error(f"Error occurred while checking compilers: {exception}")
            raise Exception(f"Error occurred while checking compilers: {exception}")
    
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

    def extract_code(self, code:str, start_sep='```', end_sep='```',skip_first_line=False,code_mode=False):
        """
        Extracts the code from the provided string.
        If the string contains the start and end separators, it extracts the code between them.
        Otherwise, it returns the original string.
        """
        try:
            has_newline = False
            if start_sep in code and end_sep in code:
                start = code.find(start_sep) + len(start_sep)
                # Skip the newline character after the start separator
                if code[start] == '\n':
                    start += 1
                    has_newline = True
                    
                end = code.find(end_sep, start)
                # Skip the newline character before the end separator
                if code[end - 1] == '\n':
                    end -= 1
                    
                if skip_first_line and code_mode and not has_newline:
                    # Skip the first line after the start separator
                    start = code.find('\n', start) + 1
                    
                extracted_code = code[start:end]
                # Remove extra words for commands present.
                if not code_mode and 'bash' in extracted_code:
                    extracted_code = extracted_code.replace('bash', '')
                
                self.logger.info("Code extracted successfully.")
                return extracted_code
            else:
                self.logger.info("No special characters found in the code. Returning the original code.")
                return code
        except Exception as exception:
            self.logger.error(f"Error occurred while extracting code: {exception}")
            raise Exception(f"Error occurred while extracting code: {exception}")
          
    def execute_code(self, code, language):
        """
        This method is used to execute the provided code in the specified language.

        Parameters:
        code (str): The code to be executed.
        language (str): The programming language in which the code is written.

        Returns:
        str: The output of the executed code.
        """
        try:
            language = language.lower()
            self.logger.info(f"Running code: {code[:100]} in language: {language}")

            # Check for code and language validity
            if not code or len(code.strip()) == 0:
                return "Code is empty. Cannot execute an empty code."
            
            # Check for compilers on the system
            compilers_status = self._check_compilers(language)
            if not compilers_status:
                raise Exception("Compilers not found. Please install compilers on your system.")
            
            if language == "python":
                process = subprocess.Popen(["python", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                stdout_output = stdout.decode("utf-8")
                stderr_output = stderr.decode("utf-8")
                self.logger.info(f"Python Output execution: {stdout_output}, Errors: {stderr_output}")
                return stdout_output, stderr_output
            
            elif language == "javascript":
                process = subprocess.Popen(["node", "-e", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                stdout_output = stdout.decode("utf-8")
                stderr_output = stderr.decode("utf-8")
                self.logger.info(f"JavaScript Output execution: {stdout_output}, Errors: {stderr_output}")
                return stdout_output, stderr_output

            elif language == "java":
                # Extract the class name from code.
                class_name_pattern = r"class ([A-Za-z0-9_]+)"
                class_name = re.search(class_name_pattern, code).group(1)
                self.logger.info(f"For Language: {language}, Class Name: {class_name}")
                
                # Write the code to a temp .java file
                tmp_dir = tempfile.TemporaryDirectory()
                java_file = os.path.join(tmp_dir.name,class_name + ".java")
                with open(java_file, "w") as file:
                    file.write(code)

                # Compile the java code 
                subprocess.run(["javac", java_file])

                # Run the compiled class
                process = subprocess.Popen(["java", "-cp", tmp_dir.name, class_name],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                # Clean up the temporary directory
                tmp_dir.cleanup()

                stdout_output = stdout.decode("utf-8")
                stderr_output = stderr.decode("utf-8")

                self.logger.info(f"Java Output: {stdout_output}")
                self.logger.info(f"Java Errors: {stderr_output}")

                return stdout_output, stderr_output

            elif language == "cpp":
                with open('temp.cpp', 'w') as file:
                    file.write(code)
                    
                compile_process = subprocess.Popen(["g++", "-std=c++17", "temp.cpp", "-o", "temp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = compile_process.communicate()
                if compile_process.returncode != 0:  # Compilation failed
                    stdout_output = stdout.decode("utf-8")
                    stderr_output = stderr.decode("utf-8")
                    self.logger.info(f"C++ Compilation Errors: {stderr_output}")
                    # remove the temp file
                    os.remove("temp.cpp")
                    return stdout_output, stderr_output
                else:  # Compilation succeeded, now run the program
                    run_process = subprocess.Popen(["./temp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = run_process.communicate()
                    stdout_output = stdout.decode("utf-8")
                    stderr_output = stderr.decode("utf-8")
                    self.logger.info(f"C++ Output execution: {stdout_output}, Errors: {stderr_output}")
                    # remove the temp file
                    os.remove("temp.cpp")
                    return stdout_output, stderr_output
            
            else:
                self.logger.info("Unsupported language.")
                raise Exception("Unsupported language.")
                
        except Exception as exception:
            self.logger.error(f"Exception in running code: {str(exception)}")
            raise exception
        
    def execute_script(self, script:str, os_type:str='macos'):
        output = error = None
        try:
            if not script:
                raise ValueError("Script must be provided.")
            if not os_type:
                raise ValueError("OS type must be provided.")
            
            self.logger.info(f"Attempting to execute script: {script[:50]}")
            if os_type.lower() == 'macos':
                output, error = self._execute_script(script, shell='applescript')
            elif os_type.lower() == 'linux':
                output, error = self._execute_script(script, shell='bash')
            elif os_type.lower() == 'windows':
                output, error = self._execute_script(script, shell='powershell')
            else:
                raise ValueError("Invalid OS type. Please provide 'macos', 'linux', or 'windows'.")
            
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