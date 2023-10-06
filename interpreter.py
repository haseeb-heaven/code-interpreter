import argparse
import json
import sys
import traceback
import random
from datetime import datetime
from libs.code_interpreter import CodeInterpreter
from huggingface_hub import InferenceClient
from libs.logger import initialize_logger
from libs.markdown_code import display_code, display_markdown_message
from libs.package_installer import PackageInstaller
from libs.helper_utils import HelperUtils

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

def get_prompt(message: str, chat_history: list[tuple[str, str]],system_prompt: str) -> str:
    texts = [f'<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n']
    do_strip = False
    for user_input, response in chat_history:
        user_input = user_input.strip() if do_strip else user_input
        do_strip = True
        texts.append(f'{user_input} [/INST] {response.strip()} </s><s>[INST] ')
    message = message.strip() if do_strip else message
    texts.append(f'{message} [/INST]')
    return ''.join(texts)
    
def generate_text(message, chat_history: list[tuple[str, str]], temperature=0.9, max_new_tokens=512, top_p=0.95, repetition_penalty=1.0, config_values=None):
    logger.debug("Generating code.")
    
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

    prompt = get_prompt(message, chat_history, DEFAULT_SYSTEM_PROMPT)
    
    stream = client.text_generation(prompt, **generate_kwargs, stream=False, details=True, return_full_text=False)
    logger.debug(f"Generated code {stream.generated_text}")
    return stream.generated_text

def llama_main(args):
    history = []
    INTERPRETER_LANGUAGE = args.lang if args.lang else 'python'
    SAVE_CODE = args.save_code
    EXECUTE_CODE = args.exec
    DISPLAY_CODE = args.display_code
    
    # Initialize the logger.
    global logger
    logger = initialize_logger("logs/interpreter.log")
    
    # Initialize the HelperUtils class
    helper_utils = HelperUtils()
    
    # Get all values from config file
    config_values = helper_utils.read_config_file()
    # Store all values to variables
    for key, value in config_values.items():
        globals()[key] = value
    
    # Initialize the InferenceClient with the model "codellama/CodeLlama-34b-Instruct-hf"
    global client
    HF_MODEL = str(config_values.get('HF_MODEL', "codellama/CodeLlama-34b-Instruct-h"))
    logger.info(f"Using model {HF_MODEL}")
    client = InferenceClient(HF_MODEL)
    
    # Update the mode based on the string value of args.mode
    CODE_MODE = True if args.mode == 'code' else False
    SCRIPT_MODE = True if args.mode == 'script' else False
    COMMAND_MODE = True if args.mode == 'command' else False
    
    # Set the code mode to True if the script mode or command mode is selected
    if not SCRIPT_MODE and not COMMAND_MODE:
        CODE_MODE = True
        
    print("Llama Interpreter - v 1.0")
    code_interpreter = CodeInterpreter()
    package_installer = PackageInstaller()
    
    # Get the OS Platform and version.
    os_platform = helper_utils.get_os_platform()
    os_name = os_platform[0]
    os_version = os_platform[1]
    command_mode = 'Code'
    
    # Display the OS and language selected
    mode = 'Script' if SCRIPT_MODE else 'Command' if COMMAND_MODE else 'Code'
    display_code(f"OS: '{os_name}', Language: '{INTERPRETER_LANGUAGE}', Mode: '{mode}' Model: {HF_MODEL}")
    command_mode = mode
    
   # Call this function before your main loop
    helper_utils.initialize_readline_history()
    
    skip_first_line = config_values.get('skip_first_line', 'False') == 'True'
    logger.info(f"Skip first line: {skip_first_line}")
            
    while True:
        try:
            # Define the task
            task = input("> ")
            if task.lower() in ['exit', 'quit']:
                print("Exiting CodeLlama Chat.")
                break
            
            prompt = ""
            current_time = datetime.now().strftime("%H%M%S")
            # Combine the task and specifications into a single prompt
            if CODE_MODE:
                prompt = f"Generate the code in {INTERPRETER_LANGUAGE} language for this task '{task} for Operating System: {os_name}'."
                history.append((task,prompt))
            
            elif SCRIPT_MODE:
                language_map = {'macos': 'applescript', 'linux': 'bash', 'windows': 'powershell'}
                INTERPRETER_LANGUAGE = language_map.get(os_name.lower(), 'python')
                script_type = 'Apple script' if os_name.lower() == 'macos' else 'Bash Shell script' if os_name.lower() == 'linux' else 'Powershell script' if os_name.lower() == 'windows' else 'script'
                prompt += f"\nGenerate {script_type} for this prompt and make this script easy to read and understand for this task '{task} for Operating System is {os_name}'."
                
            elif COMMAND_MODE:
                prompt = f"Generate the single terminal command for this task '{task} for Operating System is {os_name}'."
            logger.debug(f"Prompt: {prompt}")
            
            
            generated_output = generate_text(prompt, history, config_values=config_values)
            logger.info(f"Generated output type {type(generated_output)}")
            
            # Extract code from generated output
            extracted_code = code_interpreter.extract_code(generated_output,skip_first_line=skip_first_line)
            logger.info(f"Extracted code: {extracted_code[:50]}")
            
            # Display extracted code
            if DISPLAY_CODE:
                display_code(extracted_code)
                logger.info("Code extracted successfully.")
            
            if extracted_code:
                if INTERPRETER_LANGUAGE == 'javascript' and SAVE_CODE:
                    code_interpreter.save_code(f"output/code_generated_{current_time}.js",extracted_code)
                    logger.info(f"JavaScript code saved successfully.")
                    
                elif INTERPRETER_LANGUAGE == 'python' and SAVE_CODE:
                    code_interpreter.save_code(f"output/code_generated_{current_time}.py",extracted_code)
                    logger.info(f"Python code saved successfully.")
                
                if EXECUTE_CODE:
                    execute = 'y'
                else:
                    # Ask for user confirmation before executing the extracted code
                    execute = input("Execute the code? (Y/N): ")
                    
                if execute.lower() == 'y':
                    try:
                        code_output = ""
                        code_error = ""
                        logger.info(f"Extracted {INTERPRETER_LANGUAGE} code: {extracted_code[:50]}")
                        
                        if SCRIPT_MODE:
                            code_output,code_error = code_interpreter.execute_script(extracted_code,os_type=os_name)
                        elif COMMAND_MODE:
                            code_output,code_error = code_interpreter.execute_command(extracted_code)
                        elif CODE_MODE:
                            code_output,code_error = code_interpreter.execute_code(extracted_code,language=INTERPRETER_LANGUAGE)
                        
                        package_name = None
                        
                        if code_error and len(code_error) > 0:
                            # Install the missing package on error.
                            if INTERPRETER_LANGUAGE == 'javascript' and "Cannot find module" in code_error:
                                package_name = package_installer.extract_javascript_package_name(code_error)
                                    
                            # Install the missing package on error.
                            if INTERPRETER_LANGUAGE == 'python' and "ModuleNotFoundError" in code_error or "No module named" in code_error:
                                package_name = package_installer.extract_python_package_name(code_error)
                                
                            if package_name:
                                logger.info(f"Trying to install missing package **'{package_name}'** on error")
                                display_markdown_message(f"Installing missing package **'{package_name}'** on error")
                                package_installer.install_package(package_name,language=INTERPRETER_LANGUAGE)
                            
                        if code_output and code_output != None and code_output.__len__() > 0:
                            logger.info(f"{INTERPRETER_LANGUAGE} code executed successfully.")
                            display_code(code_output)
                            logger.info(f"Output: {code_output[:100]}")
                        
                        elif code_error:
                            logger.info(f"Python code executed with error.")
                            display_markdown_message(f"Error: {code_error}")
                            
                    except Exception as exception:
                        raise exception
            helper_utils.save_history_json(task, command_mode, os_name, INTERPRETER_LANGUAGE, prompt, extracted_code)
            
        except Exception as exception:
            # print the traceback
            import traceback
            traceback.print_exc()
            logger.error(f"Error occurred: {str(exception)}")
            raise exception
    
# App main entry point.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='LLama - Interpreter')
        parser.add_argument('--exec', '-e', action='store_true', help='Execute the code')
        parser.add_argument('--save_code', '-s', action='store_true', help='Save the generated code')
        parser.add_argument('--mode', '-m', choices=['code', 'script', 'command'], help='Select the mode (`code` for generating code, `script` for generating shell scripts, `command` for generating single line commands)')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0')
        parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language. (Defaults to Python)')
        parser.add_argument('--display_code', '-dc', action='store_true', help='Display the code in output')
        args = parser.parse_args()
        
        # Check if only the application name is passed
        if len(sys.argv) <= 1:
            parser.print_help()
            sys.exit(1)
        
        # Call the main method.
        llama_main(args)
    except Exception as exception:
        logger.error(f"Error occurred: {str(exception)}")
        traceback.print_exc()
