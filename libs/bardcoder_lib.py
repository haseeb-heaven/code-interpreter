"""
Details : BardCoder Library is code genrator for bard. It is used to generate code from bard response.
its using Bard API to interact with bard and refine the results for coding purpose.
The main purpose of this is to integrate bard with any projects and make code generation easy.
Language : Python
Author : HeavenHM.
License : MIT
Date : 21-05-2023
"""
import logging
import pprint
import os
import subprocess
import traceback
import google.generativeai as palm
from dotenv import load_dotenv
from libs.logger import logger
from libs.code_executor import CodeExecutor

# Set up logging
logging.basicConfig(filename='palm-coder.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BardCoder:
    def __init__(self, api_key, model="text-bison-001", temperature=0.3, max_output_tokens=2048, mode="balanced", guidelines=None):
        """
        Initialize the BardCoder class with the given parameters.
        """
        try:
            self.model = "models/" + model
            self.temperature = temperature
            self.max_output_tokens = max_output_tokens
            self.mode = mode
            self.api_key = None
            self.top_k = 20
            self.top_p = 0.85
            self.guidelines = guidelines if guidelines else []
            self.code = None
            self.extracted_code = None
            self.palm_generator = None
            self.validate_api_key(api_key)  # Validate the API key before configuring the API
            self._configure_api(api_key)
            self.code_executor = CodeExecutor('offline',self.code,"python",".py")

            # Dynamically construct guidelines based on session state
            self.guidelines_list = []

            if "modular_code" in self.guidelines:
                self.guidelines_list.append("- Ensure the method is modular in its approach.")
            if "exception_handling" in self.guidelines:
                self.guidelines_list.append("- Integrate robust exception handling.")
            if "error_handling" in self.guidelines:
                self.guidelines_list.append("- Add error handling to each module.")
            if "efficient_code" in self.guidelines:
                self.guidelines_list.append("- Optimize the code to ensure it runs efficiently.")
            if "robust_code" in self.guidelines:
                self.guidelines_list.append("- Ensure the code is robust against potential issues.")
            if "naming_conventions" in self.guidelines:
                self.guidelines_list.append("- Follow standard naming conventions.")
            if "documentation" in self.guidelines:
                self.guidelines_list.append("- Document the code.")
            if "code_only" in self.guidelines:
                self.guidelines_list.append("- Generate code only and make sure there are no comments generated or docs alongside the code and dont ask input from the user of any kind")
            if "script_only" in self.guidelines:
                self.guidelines_list.append("- Generate the code like script in such a way that there should not be any method or comments defined in code just code line by line written\nAttention: There should be no comments in the code.")
            # Convert the list to a string
            self.guidelines = "\n".join(self.guidelines_list)
        except:
            raise

    def validate_api_key(self, api_key):
        """
        Validate the API key based on the given criteria.
        """
        if " " in api_key:
            raise ValueError("API key should not contain spaces.")
        if api_key.islower():
            raise ValueError("API key should not contain only lower case characters.")
        if api_key.isupper():
            raise ValueError("API key should not contain only upper case characters.")
        if len(api_key) < 30:
            raise ValueError("API key should be at least 30 characters long.")

    def _configure_api(self,api_key=None):
        """
        Configure the palm API with the API key from the environment.
        """
        try:
            if api_key is None or len(api_key) == 0:
                load_dotenv()
                self.api_key = os.getenv('PALMAI_API_KEY')
                logger.info("API key loaded from environment variables.")
            else:
                self.api_key = api_key
                logger.info("API key provided from settings.")
            palm.configure(api_key=self.api_key)
            logger.info("Palm API configured successfully.")
        except Exception as e:
            logger.error(f"Error occurred while configuring Palm API: {e}")

    def _extract_code(self, code):
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
                logger.info("Code extracted successfully.")
                return extracted_code
            else:
                logger.info("No special characters found in the code. Returning the original code.")
                return code
        except Exception as e:
            logger.error(f"Error occurred while extracting code: {e}")
            return None
    
    def generate_code(self, code_prompt,code_language='python'):
        """
        Function to generate text using the palm API.
        """
        try:
            # Defining the properties.
            if self.mode == "precise":
                self.top_k = 40
                self.top_p = 0.95
                self.temprature = 0
            elif self.mode == "balanced":
                self.top_k = 20
                self.top_p = 0.85
                self.temprature = 0.3
            elif self.mode == "creative":
                self.top_k = 10
                self.top_p = 0.75
                self.temprature = 1
            else:
                raise ValueError("Invalid mode. Choose from 'precise', 'balanced', 'creative'.")

            logger.info(f"Generating code with mode: {self.mode}, top_k: {self.top_k}, top_p: {self.top_p}")

            
            # check for valid prompt and language
            if not code_prompt or len(code_prompt) == 0:
                logger.error("Error in code generation: Please enter a valid prompt.")
                return
            
            logger.info(f"Generating code for prompt: {code_prompt} in language: {code_language}")
            if code_prompt and len(code_prompt) > 0 and code_language and len(code_language) > 0:
                logger.info(f"Generating code for prompt: {code_prompt} in language: {code_language}")
                
            # Construct the prompt
            prompt = f"""
            Task: Design a program {code_prompt} with the following guidelines and
            make sure the output is printed on the screen.
            And make sure the output contains only the code and nothing else.

            Guidelines:
            {self.guidelines}
            """
            
            logger.info(f"Prompt constructed successfully: {prompt}")

            self.palm_generator = palm.generate_text(
                model=self.model,
                prompt=prompt,
                candidate_count=4,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                top_k=self.top_k,
                top_p=self.top_p,
                stop_sequences=[],
                safety_settings=[],  # Empty list to disable the harm categories
             )
            
            if self.palm_generator:
                # extract the code from the palm completion
                self.code = self.palm_generator.result
                # raise exception if self.code is empty or invalid
                if self.code is None or len(self.code) == 0:
                    raise ValueError("Generated code is empty or invalid.")
                
                logger.info(f"Palm coder is initialized.")
                logger.info(f"Generated code: {self.code[:100]}...")
            
            if self.palm_generator:
                # Extracted code from the palm completion
                self.extracted_code = self._extract_code(self.code)
                
                # Set Executor class vars
                self.code_executor.code = self.code
                self.code_executor.extracted_code = self.extracted_code
                
                # Check if the code or extracted code is not empty or null
                if not self.code or not self.extracted_code:
                    raise Exception("Error: Generated code or extracted code is empty or null.")
                
                return self.extracted_code
            else:
                raise Exception("Error in code generation: Please enter a valid code.")
            
        except Exception as exception:
            logger.error(f"Error in code generation: {traceback.format_exc()}")
            raise Exception(exception)

    def fix_code(self, code,code_error,code_language='python'):
        """
        Function to fix the generated code using the palm API.
        """
        try:
            # Check for valid code
            if not code or len(code) == 0:
                logger.error("Error in code fixing: Please enter a valid code.")
                return
            
            logger.info(f"Fixing code")
            if code and len(code) > 0:
                logger.info(f"Fixing code {code[:100]}... in language {code_language}")
                
                # This template is used to generate the prompt for fixing the code
                template = f"""
                Task: Fix the following program {{code}} with the following error '{code_error}' in the language {code_language} with the following guidelines
                Make sure the output is printed on the screen.
                And make sure the output contains the full fixed code.
                Add comments in that line where you fixed and what you fixed.
                """
                
                # Prompt Templates
                code_template = template.format(code=code)
                
                # LLM Chains definition
                # Create a chain that generates the code
                self.palm_generator = palm.generate_text(
                model=self.model,
                prompt=code_template,
                candidate_count=4,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                top_k=self.top_k,
                top_p=self.top_p,
                stop_sequences=[]
                )
                
                if self.palm_generator:
                    # Extracted code from the palm completion
                    code = self.palm_generator.result
                    extracted_code = self._extract_code(code)
                    
                    # Check if the code or extracted code is not empty or null
                    if not code or not extracted_code:
                        raise Exception("Error: Generated code or extracted code is empty or null.")
                    else:
                        return extracted_code
                else:
                    raise Exception("Error in code fixing: Please enter a valid code.")
            else:
                logger.error("Error in code fixing: Please enter a valid code and language.")
        except:
            logger.error(f"Error in code fixing: {traceback.format_exc()}")
            
    def save_code(self,code_file:str):
        try:
            if not self.code or not code_file:
                raise ValueError("Both code and filename must be provided.")
            
            logger.info(f"Attempting to save {self.code[:50]} to file: {code_file}")
            self.code_executor.extracted_code = self.extracted_code
            saved_file = self.code_executor.save_code(self.code,code_file)
            logger.info(f"Code saved successfully to file: {saved_file}")
            return saved_file
        except:
            if traceback.format_exc() is not None:
                logger.error(f"Error in saving code to file: {traceback.format_exc()}")
            raise Exception("Error in saving code to file.")

    def execute_code(self,code:str,language: str='python', compiler_mode: str='offline'):
        if not code or not language or not compiler_mode:
            raise ValueError("Code, language, and compiler mode must be provided.")
        try:
            logger.info(f"Attempting to execute code: {code[:50]} in language: {language} with Compiler Mode: {compiler_mode}")
            output,error = self.code_executor.execute_code(code, language,compiler_mode)
            logger.info(f"Code executed successfully with output: {output[:100]}...")
            if output:
                logger.info(f"Code executed successfully.")
            elif error:
                logger.info(f"Code executed with error: {error}...")
                
            return output,error
        except Exception as exception:
            logger.error(f"Error in executing code: {traceback.format_exc()}")
            raise Exception(exception)
    
    def execute_script(self, script:str, os_type:str='macos'):
        output = error = None
        try:
            if not script:
                raise ValueError("Script must be provided.")
            if not os_type:
                raise ValueError("OS type must be provided.")
            
            logger.info(f"Attempting to execute script: {script[:50]}")
            if os_type.lower() == 'macos':
                output, error = self.code_executor.run_apple_script(script)
            elif os_type.lower() == 'linux':
                output, error = self.code_executor.run_bash_script(script)
            elif os_type.lower() == 'windows':
                output, error = self.code_executor.run_powershell_script(script)
            else:
                raise ValueError("Invalid OS type. Please provide 'macos', 'linux', or 'windows'.")
            
            if output:
                logger.info(f"Script executed successfully with output: {output[:50]}...")
            if error:
                logger.error(f"Script executed with error: {error}...")
        except Exception as exception:
            logger.error(f"Error in executing script: {traceback.format_exc()}")
            error = str(exception)
        finally:
            return output, error
    
    def get_code_extension(self,code=None):
        try:
            return self.code_executor.get_code_extension(code=None)
        except Exception as exception:
            logger.error(f"Error in getting code extension: {traceback.format_exc()}")
            raise Exception(exception)
