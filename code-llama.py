import argparse
import json
import os
import sys
import traceback
import logging
import random
from datetime import datetime
from libs.code_interpreter_lib import CodeInterpreter
from huggingface_hub import InferenceClient
from libs.markdown_code import display_code, display_markdown_message
from libs.package_installer import PackageInstaller

# Initialize logger
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('logs/code-llama.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

client = InferenceClient(
    "codellama/CodeLlama-34b-Instruct-hf"
    #"mistralai/Mistral-7B-Instruct-v0.1"
)

DEFAULT_SYSTEM_PROMPT = """\
As 'code-generator', your sole role is to generate code. The code should:
- Be sequential in code.
- Be devoid of comments.
- Not ask for user input.
- Not contain explanations or additional text.
- Not be modular.
Remember, you can only output code and nothing else you don't have ability to respond in plain text.
"""

def get_prompt(message: str, chat_history: list[tuple[str, str]],system_prompt: str) -> str:
    texts = [f'<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n']
    # The first user input is _not_ stripped
    do_strip = False
    for user_input, response in chat_history:
        user_input = user_input.strip() if do_strip else user_input
        do_strip = True
        texts.append(f'{user_input} [/INST] {response.strip()} </s><s>[INST] ')
    message = message.strip() if do_strip else message
    texts.append(f'{message} [/INST]')
    return ''.join(texts)

def generate_text(message,chat_history: list[tuple[str, str]], temperature=0.9, max_new_tokens=512, top_p=0.95, repetition_penalty=1.0):
    logger.debug("Generating code.")
    temperature = float(temperature)
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

def get_os_platform():
    try:
        import platform
        os_info = platform.uname()
        os_name = os_info.system

        # Map the system attribute to the desired format
        os_name_mapping = {
            'Darwin': 'MacOS',
            'Linux': 'Linux',
            'Windows': 'Windows'
        }

        os_name = os_name_mapping.get(os_name, 'Other')

        logger.info(f"Operating System: {os_name} Version: {os_info.version}")
        return os_name, os_info.version
    except Exception as exception:
        logger.error(f"Error in checking OS and version: {str(exception)}")
        raise Exception(f"Error in checking OS and version: {str(exception)}")

def save_history_json(task, mode, os_name, language, prompt, extracted_code, filename):
    history_entry = {
        "Assistant": {
            "Task": task,
            "Mode": mode,
            "OS detected": os_name,
            "Language selected": language
        },
        "User": prompt,
        "System": extracted_code
    }

    # Check if file exists and it is not empty
    if os.path.isfile(filename) and os.path.getsize(filename) > 0:
        # If file exists and is not empty, load its contents
        with open(filename, "r") as history_file:
            data = json.load(history_file)
    else:
        # If file doesn't exist or is empty, initialize an empty list
        data = []

    # Append new data
    data.append(history_entry)

    # Write updated data back to file
    with open(filename, "w") as history_file:
        json.dump(data, history_file)

def llama_main(args):
    history = []
    INTERPRETER_LANGUAGE = args.lang if args.lang else 'javascript'
    SAVE_CODE = args.save_code
    EXECUTE_CODE = args.exec
    SCRIPT_MODE = args.script
    DISPLAY_CODE = args.display_code
    COMMAND_MODE = args.command
    
    print("Llama Interpreter - v 1.0")
    code_interpreter = CodeInterpreter()
    package_installer = PackageInstaller()
    
    # Get the OS Platform and version.
    os_platform = get_os_platform()
    os_name = os_platform[0]
    os_version = os_platform[1]
    command_mode = 'Code'
    
    # Display the OS and language selected
    display_code(f"OS detected: '{os_name}'")
    display_code(f"Language selected: '{INTERPRETER_LANGUAGE}'")
    if SCRIPT_MODE:
        display_code(f"Mode selected: 'Script'")
        command_mode = 'Script'
    elif COMMAND_MODE:
        display_code(f"Mode selected: 'Command'")
        command_mode = 'Command'
    else:
        display_code(f"Mode selected: 'Code'")
        command_mode = 'Code'
    
    # Open the history file to save the data.
    history_file_name = "history/history.json"
    
    history_file = open(history_file_name, "a")
    
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
            if not SCRIPT_MODE and not COMMAND_MODE:
                prompt = f"Generate the code add main method as well in {INTERPRETER_LANGUAGE} programming language for this task '{task} for Operating System is {os_name}'."
                history.append((task,prompt))
            
            elif SCRIPT_MODE:
                display_markdown_message(f"**Script** mode is selected")
                if os_name.lower() == 'macos':  # MacOS
                    INTERPRETER_LANGUAGE = 'applescript'
                    prompt += "\nGenerate Apple script for this prompt and make this script easy to read and understand"
                elif os_name.lower() == 'linux':  # Linux
                    INTERPRETER_LANGUAGE = 'bash'
                    prompt += "\nGenerate Bash Shell script for this prompt and make this script easy to read and understand"
                elif os_name.lower() == 'windows':  # Windows
                    INTERPRETER_LANGUAGE = 'powershell'
                    prompt += "\nGenerate Powershell script for this prompt and make this script easy to read and understand"
                else:
                    INTERPRETER_LANGUAGE = 'python'
                    prompt += "\nGenerate a script for this prompt and make this script easy to read and understand"
                prompt += f"\nfor this task '{task} for Operating System is {os_name}'."
                
            elif COMMAND_MODE:
                display_markdown_message(f"**Command** mode is selected")
                prompt = f"Generate the single terminal command for this task '{task} for Operating System is {os_name}'."
            logger.debug(f"Prompt: {prompt}")
            
            
            generated_output = generate_text(prompt,history,temperature=0.1,max_new_tokens=2048)
            logger.info(f"Generated output type {type(generated_output)}")
            
            # Extract code from generated output
            extracted_code = code_interpreter.extract_code(generated_output)
            logger.info(f"Extracted code: {extracted_code[:50]}")
            
            # Display extracted code
            if DISPLAY_CODE:
                display_code(extracted_code)
                logger.info("Code extracted successfully.")
            
            if extracted_code:
                if INTERPRETER_LANGUAGE == 'javascript' and SAVE_CODE:
                    code_interpreter.save_code("code_generated.js",extracted_code)
                    logger.info(f"JavaScript code saved successfully.")
                    
                elif INTERPRETER_LANGUAGE == 'python' and SAVE_CODE:
                    code_interpreter.save_code("code_generated.py",extracted_code)
                    logger.info(f"Python code saved successfully.")
                
                if EXECUTE_CODE:
                    execute = 'y'
                else:
                    # Ask for user confirmation before executing the extracted code
                    execute = input("Do you want to execute the extracted code? (Y/N): ")
                    
                if execute.lower() == 'y':
                    try:
                        logger.info(f"Extracted {INTERPRETER_LANGUAGE} code: {extracted_code[:50]}")
                        
                        if args.script:
                            code_output,code_error = code_interpreter.execute_script(extracted_code,os_type=os_name)
                        elif COMMAND_MODE:
                            code_output,code_error = code_interpreter.execute_command(extracted_code)
                        else:
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
                        
                        elif code_error:
                            logger.info(f"Python code executed with error.")
                            display_markdown_message(f"Error: {code_error}")
                            
                        logger.info(f"Output: {code_output}")
                    except Exception as exception:
                        raise exception
            save_history_json(task, command_mode, os_name, INTERPRETER_LANGUAGE, prompt, extracted_code, history_file_name)
            
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
        parser.add_argument('--script', '-sc', action='store_true', help='Execute the shell script')
        parser.add_argument('--command', '-c', action='store_true', help='Execute the command')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0')
        parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language')
        parser.add_argument('--display_code', '-dc', action='store_true', help='Display the code in output')
        args = parser.parse_args()
        
        # Check if only the application name is passed
        if len(sys.argv) == 0 and sys.argv[0] == parser.prog:
            display_markdown_message("**Usage: python interpreter.py [options]**")
            display_markdown_message("**Options:**")
            display_markdown_message("**--exec, -e: Execute the code**")
            display_markdown_message("**--save_code: Save the generated code**")
            display_markdown_message("**--script, -sc: Execute the shell script**")
            display_markdown_message("**--command, -c: Execute the command**")
            display_markdown_message("**--version: Show the version of the program**")
            display_markdown_message("**--lang, -l: Set the interpreter language**")
            sys.exit(1)
        
        # Call the main bard.
        llama_main(args)
    except Exception as exception:
        logger.error(f"Error occurred: {str(exception)}")
        traceback.print_exc()
