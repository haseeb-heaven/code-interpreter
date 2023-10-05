# general_utils.py
import base64
import os
import tempfile
from libs.logger import logger
import subprocess
import traceback
import libs.extensions_map as extensions_map
from libs.extensions_map import get_file_extesion

def LangCodes():
    
    LANGUAGE_CODES = {
        'C': 'c',
        'C++': 'cpp',
        'Java': 'java',
        'Ruby': 'ruby',
        'Scala': 'scala',
        'C#': 'csharp',
        'Objective C': 'objc',
        'Swift': 'swift',
        'JavaScript': 'nodejs',
        'Kotlin': 'kotlin',
        'Python': 'python3',
        'GO Lang': 'go',
    }
    return LANGUAGE_CODES

class CodeExecutor:
    def __init__(self, compiler_mode: str, code: str,language: str,code_extenstion: str):
        self.compiler_mode = compiler_mode
        self.language = language
        self.code = code
        self.extracted_code = code
        self.code_extenstion = code_extenstion
        
    def run_apple_script(self, script: str):
        stdout = stderr = None
        try:
            logger.info("Running AppleScript")
            process = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(script.encode())
            logger.info(f"Output is {stdout.decode()} and error is {stderr.decode()}")
            if process.returncode != 0:
                logger.error(f"Error in running AppleScript: {stderr.decode()}")
        except Exception as exception:
            logger.error(f"Exception in running AppleScript: {str(exception)}")
            stderr = str(exception)
        finally:
            return stdout.decode().strip() if stdout else None, stderr.decode().strip() if stderr else None

    def execute_code(self,code:str,language: str='python', compiler_mode: str='offline'):
        
        if not code or len(code.strip()) == 0 or not language or len(language.strip()) == 0:
            logger.error("Error in code execution: Generated code is empty.")
            return
        
        logger.info(f"Executing code: {code[:50]} in language: {language} with Compiler Mode: {compiler_mode}")

        try:
            if len(code) == 0 or code == "":
                raise Exception("Execution code is empty or null")
            
            if compiler_mode.lower() == "online":
                html_content = self.generate_dynamic_html(language, code)
                logger.info(f"HTML Template: {html_content[:100]}")
                return html_content

            else:
                output,error = self.run_code(code, language)
                logger.info(f"Runner Output execution: {output} and error: {error}")
                return output,error

        except Exception:
            logger.error(f"Error in code execution: {traceback.format_exc()}")

    def check_compilers(self, language):
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
            logger.error("Invalid language selected.")
            return False

        compiler = subprocess.run(compilers[language], capture_output=True, text=True)
        if compiler.returncode != 0:
            logger.error(f"{language.capitalize()} compiler not found.")
            return False

        return True
    
    def run_code(self,code, language):
        language = language.lower()
        logger.info(f"Running code: {code[:100]} in language: {language}")

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
            logger.info(f"Runner Output execution: {stdout_output}, Errors: {stderr_output}")
            return stdout_output, stderr_output

        elif language == "c" or language == "c++":
            compile_output = subprocess.run(
                ["gcc" if language == "c" else "g++", "-x", language, "-"], input=code, capture_output=True, text=True)
            if compile_output.returncode != 0:
                logger.info(f"Compiler Output: {compile_output.stderr}")
                return compile_output.stderr
            run_output = subprocess.run([compile_output.stdout], capture_output=True, text=True)
            logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
            return run_output.stdout + run_output.stderr

        elif language == "javascript":
            output = subprocess.run(["node", "-e", code], capture_output=True, text=True)
            logger.info(f"Runner Output: {output.stdout + output.stderr}")
            return output.stdout + output.stderr
            
        elif language == "java":
            classname = "Main"  # Assuming the class name is Main, adjust if needed
            compile_output = subprocess.run(["javac", "-"], input=code, capture_output=True, text=True)
            if compile_output.returncode != 0:
                logger.info(f"Compiler Output: {compile_output.stderr}")
                return compile_output.stderr
            run_output = subprocess.run(["java", "-cp", ".", classname], capture_output=True, text=True)
            logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
            return run_output.stdout + run_output.stderr

        elif language == "swift":
            output = subprocess.run(["swift", "-"], input=code, capture_output=True, text=True)
            logger.info(f"Runner Output: {output.stdout + output.stderr}")
            return output.stdout + output.stderr

        elif language == "c#":
            compile_output = subprocess.run(["csc", "-"], input=code, capture_output=True, text=True)
            if compile_output.returncode != 0:
                logger.info(f"Compiler Output: {compile_output.stderr}")
                return compile_output.stderr
            run_output = subprocess.run([compile_output.stdout], capture_output=True, text=True)
            logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
            return run_output.stdout + run_output.stderr

        elif language == "scala":
            output = subprocess.run(["scala", "-e", code], capture_output=True, text=True)
            logger.info(f"Runner Output: {output.stdout + output.stderr}")
            return output.stdout + output.stderr

        elif language == "ruby":
            output = subprocess.run(["ruby", "-e", code], capture_output=True, text=True)
            logger.info(f"Runner Output: {output.stdout + output.stderr}")
            return output.stdout + output.stderr

        elif language == "kotlin":
            compile_output = subprocess.run(["kotlinc", "-script", "-"], input=code, capture_output=True, text=True)
            if compile_output.returncode != 0:
                logger.info(f"Compiler Output: {compile_output.stderr}")
                return compile_output.stderr
            run_output = subprocess.run(["java", "-jar", compile_output.stdout], capture_output=True, text=True)
            logger.info(f"Runner Output: {run_output.stdout + run_output.stderr}")
            return run_output.stdout + run_output.stderr

        elif language == "go":
            compile_output = subprocess.run(["go", "run", "-"], input=code, capture_output=True, text=True)
            if compile_output.returncode != 0:
                logger.info(f"Compiler Output: {compile_output.stderr}")
                return compile_output.stderr
            logger.info(f"Runner Output: {compile_output.stdout + compile_output.stderr}")
            return compile_output.stdout + compile_output.stderr
        else:
            logger.info("Unsupported language.")
            return "Unsupported language."
        
    # Generate Dynamic HTML for JDoodle Compiler iFrame Embedding.
    def generate_dynamic_html(self,language, code_prompt):
        logger.info("Generating dynamic HTML for language: %s", language)
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Online JDoodle Compiler</title>
        </head>
        <body>
            <div data-pym-src='https://www.jdoodle.com/plugin' data-language="{language}"
                data-version-index="0" data-libs="" >{script_code}
            </div>
            <script src="https://www.jdoodle.com/assets/jdoodle-pym.min.js" type="text/javascript"></script>
        </body>
        </html>
        """.format(language=LangCodes()[language], script_code=code_prompt)
        return html_template
    
            # get the code extension from bard response - automatically detects the language from bard response.
    
    def get_code_extension(self, code):
        logger.info(f"Value of code is {code}")
        if code is None or not isinstance(code, str):
            raise ValueError("Code must be a non-empty string.")
        try:
            logger.info(f"Getting code extension from code {code[:50]}")
            if code and not code in "can't help":
                self.code_extension = code.split('```')[1].split('\n')[0]
                logger.info(f"Code extension: {self.code_extension}")
                return self.code_extension
        except Exception as exception:
            stack_trace = traceback.format_exc()
            logger.error(f"Error occurred while getting code extension: {exception}")
            raise Exception(stack_trace)
        return None
    
    def save_code(self, code, filename):
        if not code or not filename:
            raise ValueError("Both code and filename must be provided.")
        try:
            logger.info(f"Saving code {code[:50]} with filename: {filename}")
            self.code = code
            self.code_extenstion = '.' + self.get_code_extension(self.code)
            logger.info(f"Code extension: {self.code_extenstion}")
            if code:
                code = code.replace("\\n", "\n").replace("\\t", "\t")
                logger.info(f"Saving code with filename: {filename} and extension: {self.code_extenstion} and code: {code}")

                # Add extension to filename
                extension = extensions_map.get_file_extesion(self.code_extenstion) or self.code_extenstion
                filename = filename + extension

                with open(filename, 'w') as file:
                    file.write(self.extracted_code)
                    logger.info(f"{filename} saved.")
                return filename
        except Exception as exception:
            stack_trace = traceback.format_exc()
            logger.error(f"Error occurred while saving code: {exception}")
            raise Exception(stack_trace)
            return None

    # save multiple codes from bard response
    def save_code_choices(self, filename):
        if not filename or not isinstance(filename, str):
            raise ValueError("Filename must be a non-empty string.")
        try:
            logger.info(f"Saving code choices with filename: {filename}")
            extension = self.get_code_extension()
            if extension:
                self.code_extension = '.' + extension
                self.code_extension = extensions_map.get_file_extesion(self.code_extenstion) or self.code_extenstion

            for index, choice in enumerate(self.code_choices):
                choice_content = self.get_code_choice(index)
                logger.info(f"Enumerated Choice content: {choice}")
                self.save_file("codes/"+filename+'_'+str(index+1) + self.code_extension, choice_content)
        except Exception as exception:
            stack_trace = traceback.format_exc()
            logger.error(f"Error occurred while saving code choices: {exception}")
            raise Exception(stack_trace)
                