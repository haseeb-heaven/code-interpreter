"""
This is the ChatCoderLLM class. It provides all methods for Code LLM like Display, Execute, Format code from different llm's.
It includes features like:
- Code execution in multiple languages
- Code extraction from strings
- Saving code to a file
- Running AppleScript
- Checking for compilers
"""

import logging
import subprocess


class ChatCoderLLM:

    def __init__(self):
        self.logger = self.create_logger()

    def create_logger(self):
        """
        Creates a logger that logs to a file named 'chat-coder.log'.
        """
        try:
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.INFO)
            handler = logging.FileHandler('chat-coder.log')
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            return logger
        except Exception as exception:
            print(f"Error occurred while creating logger: {exception}")
            raise Exception(f"Error occurred while creating logger: {exception}")

    def save_code(self, filename='code_generated.py', code=None):
        """
        Saves the provided code to a file.
        The default filename is 'code_generated.py'.
        """
        try:
            with open(filename, 'w') as file:
                file.write(code)
                self.logger.info(f"Code saved successfully to {filename}.")
        except Exception as exception:
            self.logger.error(f"Error occurred while saving code to file: {exception}")
            raise Exception(f"Error occurred while saving code to file: {exception}")

    def extract_code(self, code):
        """
        Extracts the code from the provided string.
        If the string contains '```', it extracts the code between them.
        Otherwise, it returns the original string.
        """
        try:
            if '```' in code:
                start = code.find('```') + len('```\n')
                end = code.find('```', start)
                # Skip the first line after ```
                start = code.find('\n', start) + 1
                extracted_code = code[start:end]
                self.logger.info("Code extracted successfully.")
                return extracted_code
            else:
                self.logger.info("No special characters found in the code. Returning the original code.")
                return code
        except Exception as exception:
            self.logger.error(f"Error occurred while extracting code: {exception}")
            raise Exception(f"Error occurred while extracting code: {exception}")
    
    def execute_apple_script(self, script: str):
        stdout = stderr = None
        try:
            self.logger.info("Running AppleScript")
            process = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(script.encode())
            self.logger.info(f"Output is {stdout.decode()} and error is {stderr.decode()}")
            if process.returncode != 0:
                self.logger.error(f"Error in running AppleScript: {stderr.decode()}")
        except Exception as exception:
            self.logger.error(f"Exception in running AppleScript: {str(exception)}")
            stderr = str(exception)
        finally:
            return stdout.decode().strip() if stdout else None, stderr.decode().strip() if stderr else None
    
    def check_compilers(self, language):
        try:
            language = language.lower().strip()
            
            compilers = {
                "python": ["python", "--version"],
                "nodejs": ["node", "--version"],
                "c": ["gcc", "--version"],
                "c++": ["g++", "--version"],
                "csharp": ["csc", "--version"],
                "go": ["go", "version"],
                "ruby": ["ruby", "--version"],
                "java": ["java", "--version"],
                "kotlin": ["kotlinc", "--version"],
                "scala": ["scala", "--version"],
                "swift": ["swift", "--version"]
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
    
    def execute_code(self,code, language):
        try:
            language = language.lower()
            self.logger.info(f"Running code: {code[:100]} in language: {language}")

            # Check for code and language validity
            if not code or len(code.strip()) == 0:
                return "Code is empty. Cannot execute an empty code."
            
            # Check for compilers on the system
            compilers_status = self.check_compilers(language)
            if not compilers_status:
                return "Compilers not found. Please install compilers on your system."
            
            if language == "python":
                process = subprocess.Popen(["python", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                stdout_output = stdout.decode("utf-8")
                stderr_output = stderr.decode("utf-8")
                self.logger.info(f"Runner Output execution: {stdout_output}, Errors: {stderr_output}")
                return stdout_output, stderr_output

            elif language == "c" or language == "c++":
                compile_output = subprocess.run(
                    ["gcc" if language == "c" else "g++", "-x", language, "-"], input=code, capture_output=True, text=True)
                if compile_output.returncode != 0:
                    self.logger.info(f"Compiler Output: {compile_output.stderr}")
                    return compile_output.stderr
                run_output = subprocess.run([compile_output.stdout], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
                return run_output.stdout + run_output.stderr

            elif language == "javascript":
                output = subprocess.run(["node", "-e", code], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {output.stdout + output.stderr}")
                return output.stdout + output.stderr
                
            elif language == "java":
                classname = "Main"  # Assuming the class name is Main, adjust if needed
                compile_output = subprocess.run(["javac", "-"], input=code, capture_output=True, text=True)
                if compile_output.returncode != 0:
                    self.logger.info(f"Compiler Output: {compile_output.stderr}")
                    return compile_output.stderr
                run_output = subprocess.run(["java", "-cp", ".", classname], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
                return run_output.stdout + run_output.stderr

            elif language == "swift":
                output = subprocess.run(["swift", "-"], input=code, capture_output=True, text=True)
                self.logger.info(f"Runner Output: {output.stdout + output.stderr}")
                return output.stdout + output.stderr

            elif language == "c#":
                compile_output = subprocess.run(["csc", "-"], input=code, capture_output=True, text=True)
                if compile_output.returncode != 0:
                    self.logger.info(f"Compiler Output: {compile_output.stderr}")
                    return compile_output.stderr
                run_output = subprocess.run([compile_output.stdout], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
                return run_output.stdout + run_output.stderr

            elif language == "scala":
                output = subprocess.run(["scala", "-e", code], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {output.stdout + output.stderr}")
                return output.stdout + output.stderr

            elif language == "ruby":
                output = subprocess.run(["ruby", "-e", code], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {output.stdout + output.stderr}")
                return output.stdout + output.stderr

            elif language == "kotlin":
                compile_output = subprocess.run(["kotlinc", "-script", "-"], input=code, capture_output=True, text=True)
                if compile_output.returncode != 0:
                    self.logger.info(f"Compiler Output: {compile_output.stderr}")
                    return compile_output.stderr
                run_output = subprocess.run(["java", "-jar", compile_output.stdout], capture_output=True, text=True)
                self.logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
                return run_output.stdout + run_output.stderr

            elif language == "go":
                compile_output = subprocess.run(["go", "run", "-"], input=code, capture_output=True, text=True)
                if compile_output.returncode != 0:
                    self.logger.info(f"Compiler Output: {compile_output.stderr}")
                    return compile_output.stderr
                self.logger.info(f"Runner Output: {compile_output.stdout + compile_output.stderr}")
                return compile_output.stdout + compile_output.stderr
            else:
                self.logger.info("Unsupported language.")
                return "Unsupported language."
        except Exception as exception:
            self.logger.error(f"Exception in running code: {str(exception)}")
            raise exception