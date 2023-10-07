import argparse
import sys
import time
import traceback
import random
from libs.code_interpreter import CodeInterpreter
from huggingface_hub import InferenceClient
from libs.logger import initialize_logger
from libs.markdown_code import display_code, display_markdown_message
from libs.package_installer import PackageInstaller
from libs.utility_manager import UtilityManager

class Interpreter:
    logger = None
    client = None

    DEFAULT_SYSTEM_PROMPT = """\
    As 'code-generator', your sole role is to generate code. The code should:
    - Be sequential in code
    - Be devoid of comments.
    - Not ask for user input.
    - Not contain explanations or additional text.
    Remember, you can only output code and nothing else you don't have ability to respond in plain text.
    """
    
    def __init__(self, args):
        self.args = args
        self.history = []
        self.utility_manager = UtilityManager()
        self.code_interpreter = CodeInterpreter()
        self.package_installer = PackageInstaller()
        self.logger = initialize_logger("logs/interpreter.log")
        self.client = None
        self.config_values = None
        self.initialize()

    def initialize(self):
        self.INTERPRETER_LANGUAGE = self.args.lang if self.args.lang else 'python'
        self.SAVE_CODE = self.args.save_code
        self.EXECUTE_CODE = self.args.exec
        self.DISPLAY_CODE = self.args.display_code
        self.HF_MODEL = self.args.model if self.args.model else None
        self.code_llama_model = 'codellama/CodeLlama-34b-Instruct-hf'
        self.initialize_inference_client()
        self.initialize_mode()
        self.utility_manager.initialize_readline_history()

    def initialize_inference_client(self):
        hf_model_name = ""
        self.logger.info("Initializing InferenceClient")
        if self.HF_MODEL is None or self.HF_MODEL == "":
            self.logger.info("HF_MODEL is not provided, using default model.")
            self.HF_MODEL = self.code_llama_model
            hf_model_name = self.HF_MODEL.strip().split("/")[-1]
            config_file_name = f"configs/code-llama.config"
        else:
            config_file_name = f"configs/{self.HF_MODEL}.config"
        self.config_values = self.utility_manager.read_config_file(config_file_name)
        self.HF_MODEL = str(self.config_values.get('HF_MODEL', self.code_llama_model))       
        hf_model_name = self.HF_MODEL.strip().split("/")[-1]
        
        self.logger.info(f"Using model {hf_model_name}")
        self.client = InferenceClient(model=self.HF_MODEL, token=False)

    def initialize_mode(self):
        self.CODE_MODE = True if self.args.mode == 'code' else False
        self.SCRIPT_MODE = True if self.args.mode == 'script' else False
        self.COMMAND_MODE = True if self.args.mode == 'command' else False
        if not self.SCRIPT_MODE and not self.COMMAND_MODE:
            self.CODE_MODE = True

    def get_prompt(self,message: str, chat_history: list[tuple[str, str]],system_prompt: str) -> str:
        texts = [f'<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n']
        do_strip = False
        for user_input, response in chat_history:
            user_input = user_input.strip() if do_strip else user_input
            do_strip = True
            texts.append(f'{user_input} [/INST] {response.strip()} </s><s>[INST] ')
        message = message.strip() if do_strip else message
        texts.append(f'{message} [/INST]')
        return ''.join(texts)
    
    def generate_text(self,message, chat_history: list[tuple[str, str]], temperature=0.9, max_new_tokens=512, top_p=0.95, repetition_penalty=1.0, config_values=None):
        self.logger.debug("Generating code.")
        
        # Use the values from the config file if they are provided
        if config_values:
            temperature = float(config_values.get('temperature', temperature))
            max_new_tokens = int(config_values.get('max_new_tokens', max_new_tokens))
            top_p = float(config_values.get('top_p', top_p))
            repetition_penalty = float(config_values.get('repetition_penalty', repetition_penalty))

        temperature = max(temperature, 0.01)
        top_p = float(top_p)

        generate_kwargs = dict(
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            do_sample=True,
            seed=random.randint(0, 10**7),
        )

        prompt = self.get_prompt(message, chat_history, self.DEFAULT_SYSTEM_PROMPT)
        
        stream = self.client.text_generation(prompt, **generate_kwargs, stream=False, details=True, return_full_text=False)
        self.logger.debug(f"Generated code {stream.generated_text}")
        return stream.generated_text

    def handle_code_mode(self, task, os_name):
        prompt = f"Generate the code in {self.INTERPRETER_LANGUAGE} language for this task '{task} for Operating System: {os_name}'."
        self.history.append((task, prompt))
        return prompt

    def handle_script_mode(self, task, os_name):
        language_map = {'macos': 'applescript', 'linux': 'bash', 'windows': 'powershell'}
        self.INTERPRETER_LANGUAGE = language_map.get(os_name.lower(), 'python')
        
        script_type = 'Apple script' if os_name.lower() == 'macos' else 'Bash Shell script' if os_name.lower() == 'linux' else 'Powershell script' if os_name.lower() == 'windows' else 'script'
        prompt = f"\nGenerate {script_type} for this prompt and make this script easy to read and understand for this task '{task} for Operating System is {os_name}'."
        return prompt

    def handle_command_mode(self, task, os_name):
        prompt = f"Generate the single terminal command for this task '{task} for Operating System is {os_name}'."
        return prompt

    def handle_mode(self, task, os_name):
        if self.CODE_MODE:
            return self.handle_code_mode(task, os_name)
        elif self.SCRIPT_MODE:
            return self.handle_script_mode(task, os_name)
        elif self.COMMAND_MODE:
            return self.handle_command_mode(task, os_name)

    def execute_code(self, extracted_code, os_name):
        execute = 'y' if self.EXECUTE_CODE else input("Execute the code? (Y/N): ")
        if execute.lower() == 'y':
            try:
                code_output, code_error = "", ""
                if self.SCRIPT_MODE:
                    code_output, code_error = self.code_interpreter.execute_script(extracted_code, os_type=os_name)
                elif self.COMMAND_MODE:
                    code_output, code_error = self.code_interpreter.execute_command(extracted_code)
                elif self.CODE_MODE:
                    code_output, code_error = self.code_interpreter.execute_code(extracted_code, language=self.INTERPRETER_LANGUAGE)
                return code_output, code_error
            except Exception as exception:
                self.logger.error(f"Error occurred while executing code: {str(exception)}")
                return None, str(exception)  # Return error message as second element of tuple
        else:
            return None, None  # Return None, None if user chooses not to execute the code

    def interpreter_main(self):
        
        print("Code Interpreter - v 1.0")
        os_platform = self.utility_manager.get_os_platform()
        os_name = os_platform[0]
        os_version = os_platform[1]
        command_mode = 'Code'
        mode = 'Script' if self.SCRIPT_MODE else 'Command' if self.COMMAND_MODE else 'Code'
        
        display_code(f"OS: '{os_name}', Language: '{self.INTERPRETER_LANGUAGE}', Mode: '{mode}' Model: {self.HF_MODEL}")
        
        command_mode = mode
        start_sep = str(self.config_values.get('start_sep', '```'))
        end_sep = str(self.config_values.get('end_sep', '```'))
        skip_first_line = self.config_values.get('skip_first_line', 'False') == 'True'
        
        self.logger.info(f"Start separator: {start_sep}, End separator: {end_sep}, Skip first line: {skip_first_line}")
        current_time = time.strftime("%H:%M:%S", time.localtime())
        
        while True:
            try:
                
                task = input("> ")
                if task.lower() in ['exit', 'quit']:
                    break
                prompt = self.handle_mode(task, os_name)
                
                self.logger.debug(f"Prompt: {prompt}")
                generated_output = self.generate_text(prompt, self.history, config_values=self.config_values)
                
                self.logger.info(f"Generated output type {type(generated_output)}")
                extracted_code = self.code_interpreter.extract_code(generated_output, start_sep, end_sep, skip_first_line)
                
                self.logger.info(f"Extracted code: {extracted_code[:50]}")
                
                if self.DISPLAY_CODE:
                    display_code(extracted_code)
                    self.logger.info("Code extracted successfully.")
                
                if extracted_code:
                    
                    if self.INTERPRETER_LANGUAGE == 'javascript' and self.SAVE_CODE:
                        self.code_interpreter.save_code(f"output/code_generated_{current_time}.js", extracted_code)
                        self.logger.info(f"JavaScript code saved successfully.")
                    
                    elif self.INTERPRETER_LANGUAGE == 'python' and self.SAVE_CODE:
                        self.code_interpreter.save_code(f"output/code_generated_{current_time}.py", extracted_code)
                        self.logger.info(f"Python code saved successfully.")
                    
                    # Execute the code if the user has selected.
                    code_output, code_error = self.execute_code(extracted_code, os_name)
                    
                    if code_output:
                        self.logger.info(f"{self.INTERPRETER_LANGUAGE} code executed successfully.")
                        display_code(code_output)
                        self.logger.info(f"Output: {code_output[:100]}")
                    elif code_error:
                        self.logger.info(f"Python code executed with error.")
                        display_markdown_message(f"Error: {code_error}")
                
                self.utility_manager.save_history_json(task, command_mode, os_name, self.INTERPRETER_LANGUAGE, prompt, extracted_code, self.HF_MODEL)
                
            except Exception as exception:
                import traceback
                traceback.print_exc()
                self.logger.error(f"Error occurred: {str(exception)}")
                raise exception

def main():
        parser = argparse.ArgumentParser(description='Code - Interpreter')
        parser.add_argument('--exec', '-e', action='store_true', help='Execute the code')
        parser.add_argument('--save_code', '-s', action='store_true', help='Save the generated code')
        parser.add_argument('--mode', '-md', choices=['code', 'script', 'command'], help='Select the mode (`code` for generating code, `script` for generating shell scripts, `command` for generating single line commands)')
        parser.add_argument('--model', '-m', type=str, default='code-llama', help='Set the model for code generation. (Defaults to code-llama)')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0')
        parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language. (Defaults to Python)')
        parser.add_argument('--display_code', '-dc', action='store_true', help='Display the code in output')
        args = parser.parse_args()

        # Check if only the application name is passed
        if len(sys.argv) <= 1:
            parser.print_help()
            return

        # Create an instance of the Interpreter class and call the main method.
        interpreter = Interpreter(args)
        interpreter.interpreter_main()

if __name__ == "__main__":
    try:
        main()
    except:
        traceback.print_exc()