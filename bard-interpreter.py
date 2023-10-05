
import os
import sys
import time
import subprocess
import traceback
from dotenv import load_dotenv
from libs.bardcoder_lib import BardCoder
from libs.markdown_code import display_markdown_message,display_code
from libs.package_installer import PackageInstaller
from libs.logger import logger,initialize_logger

bard_coder = None
pip_installer = None
logger = None

def get_os_details():
    try:
        import platform
        import getpass
        os_info = platform.uname()
        os_name = os_info.system
        current_user = getpass.getuser()

        # Map the system attribute to the desired format
        os_name_mapping = {
            'Darwin': 'MacOS',
            'Linux': 'Linux',
            'Windows': 'Windows'
        }

        os_name = os_name_mapping.get(os_name, 'Other')

        logger.info(f"Operating System: {os_name} Version: {os_info.version} Current User: {current_user}")
        return os_name, os_info.version, current_user
    except Exception as exception:
        logger.error(f"Error in checking OS, version and current user: {str(exception)}")
        raise Exception(f"Error in checking OS, version and current user: {str(exception)}")


def setup_bard_coder():
    try:
        # load the environment variables from .env file
        load_dotenv()
        logger.info("Loaded environment variables.")

        # Initialize the bard coder
        api_key = os.getenv("PALMAI_API_KEY")  # get value of Palm API key.
        logger.info("Retrieved Palm API key.")
        # Define guidelines as a list of strings
        guidelines = ["only_code","script_only","exception_handling","error_handling"]

        # Initialize the bard coder with the defined guidelines
        bard_coder = BardCoder(api_key=api_key, model="text-bison-001", temperature=0.1, max_output_tokens=2048, mode='precise', guidelines=guidelines)
        logger.info("Initialized BardCoder.")
        return bard_coder
    except Exception as e:
        logger.error(f"Error in setting up BardCoder: {str(e)}")
        raise

def generate_code(bard_coder, prompt,language):
    try:
        # Generate the code.
        code = bard_coder.generate_code(prompt, language)  # Generate code using BardCoder
        logger.info("Generated code using BardCoder.")
        if not code:
            display_markdown_message(f"Error no data was recieved from Server")
            logger.error("No data was received from server.")
            return None
        else:
            display_code(code)
        return code
    except Exception as e:
        display_markdown_message(f"Error in generating code: {str(e)}")
        logger.error(f"Error in generating code: {str(e)}")
        return None

def execute_code(bard_coder, code,code_mode,os_type,code_language):
    max_tries = 5 # Max tries to fix code.
    delay = 5  # delay in seconds
    code_output = ""
    code_error = ""
    global pip_installer
    
    # Execute the script
    if code_mode == 'script':
        code_output,code_error = bard_coder.execute_script(code,os_type)
        if code_output and code_output != None and code_output.__len__() > 0:
            display_markdown_message(f"Output: {code_output}")
            return code_output, code_error
        
    # Execute the code.
    elif code_mode == 'code':
        code_output, code_error = bard_coder.execute_code(code)
        if code_output and code_output != None and code_output.__len__() > 0:
            display_markdown_message(f"Output: {code_output}")
            return code_output, code_error
    
    code_fixed = code
    # We will try to execute the code for a maximum number of times defined by max_tries
    for index in range(max_tries):
        try:
            # If there was an error in the previous execution of the code
            if code_error:
                                
                if 'FileNotFoundError' in code_error or 'DirectoryNotFoundError' in code_error:
                    display_markdown_message(f"Code **fixing** failed.- Exiting")
                    display_markdown_message(f"Code Error is {code_error}")
                    return code,code_error
                
                # Display a message indicating that the code execution failed and we are attempting to fix the code
                display_markdown_message(f"Execution **failed**. **Fixing code.** please wait...")
                # Attempt to fix the code using the bard_coder's fix_code method
                code_fixed = bard_coder.fix_code(code_fixed,code_error,code_language)
                
                # If the code could not be fixed, display a message and continue to the next iteration
                if code_fixed is None:
                    code_fixed = code # Reset the code back to try-again.
                    display_markdown_message(f"Code **fixing** failed.- Retring")
                    continue
                
                # Execute the fixed code
                code_output, code_error = bard_coder.execute_code(code_fixed)
                
                # If the execution of the fixed code was successful, display the output and return it
                if code_output and code_output != None and code_output.__len__() > 0:
                    display_markdown_message(f"Output: {code_output}")
                    return code_output, code_error
                else:
                    # If the execution of the fixed code was not successful, display the error
                    display_markdown_message(f"Code Error is {code_error}")
                
                # Install the missing package on error.
                if "ModuleNotFoundError" in code_error or "No module named" in code_error:
                    package_name = pip_installer.extract_package_name(code_error)
                    display_markdown_message(f"Trying to install missing package **'{package_name}'** on error")
                    pip_installer.install_package(package_name)
                    display_markdown_message(f"Successfully installed package **'{package_name}'**")
                
                
        except Exception as exception:
            display_markdown_message(f"Error in executing code: {str(exception)}")
            if index < max_tries - 1:  # it's not the final try
                time.sleep(delay)  # delay before next try
            else:  # it's the final try
                return None
            
def clean_responses():
    files_to_remove = ['graph.png', 'chart.png', 'table.md']
    for file in files_to_remove:
        try:
            if os.path.isfile(file):
                os.remove(file)
                print(f"{file} removed successfully")
        except Exception as e:
            print(f"Error in removing {file}: {str(e)}")

import argparse

def bard_main(args) -> None:
    try:
        display_markdown_message("Welcome to **PALM - Interpreter**")
        
        global logger
        logger = initialize_logger("bard-interpreter.log")
        bard_coder = setup_bard_coder()
        
        global pip_installer
        pip_installer = PackageInstaller()
        coding_language = 'python'
        
        # Get the OS Platform and version.
        os_platform = get_os_details()
        os_name = os_platform[0]
        os_version = os_platform[1]
        os_username = os_platform[2]
        
        display_code(f"Current User: {os_username}")
        display_code(f"Operating System detected {os_name}")
        
        display_markdown_message("Enter prompt (or type '**qui**t' or '**exit**' to terminate): ")
        while True:
            prompt = input("> ")
            
            # Check for termination commands
            if prompt.lower() in ['quit', 'exit']:
                display_markdown_message("Terminating **PALM - Interpreter**.")
                break
                            
            # Check if prompt is empty.
            if not prompt and prompt.__len__() == 0:
                continue
            
            # clean responses
            clean_responses()
            
            # Generate the code using PALM 2."
            # Check if --script is selected
            if args.script:
                display_markdown_message(f"**Script** mode is selected")
                if os_name.lower() == 'macos':  # MacOS
                    coding_language = 'applescript'
                    prompt += "\nGenerate Apple script for this prompt and make this script easy to read and understand"
                elif os_name.lower() == 'linux':  # Linux
                    coding_language = 'bash'
                    prompt += "\nGenerate Bash Shell script for this prompt and make this script easy to read and understand"
                elif os_name.lower() == 'windows':  # Windows
                    coding_language = 'powershell'
                    prompt += "\nGenerate Powershell script for this prompt and make this script easy to read and understand"
                else:
                    coding_language = 'python'
                    prompt += "\nGenerate a script for this prompt and make this script easy to read and understand"
                
             # Prompt for Graphs,Charts,Tables.
            if not args.script:
                display_markdown_message(f"**Code** mode is selected")
                # If graph were requested.
                if 'graph' in prompt.lower():
                    prompt += "\n" + "using Python use Matplotlib save the graph in file called 'graph.png'"

                # if Chart were requested
                if 'chart' in prompt.lower() or 'plot' in prompt.lower():
                    prompt += "\n" + "using Python use Plotly save the chart in file called 'chart.png'"

                # if Table were requested
                if 'table' in prompt.lower():
                    prompt += "\n" + "using Python use Pandas save the table in file called 'table.md'"
                
                # More guidings for Prompt.
                prompt += "\nEnsure the code is sequential, without comments, logs, documents, methods, or user input requests. Keep it short and simple."
                
                # More on system information
                prompt += "\nSystem Information: OS: " + os_name + ", OS Version: " + os_version
                
            # Generate the code using PALM 2.
            code = generate_code(bard_coder, prompt,coding_language)
            
            code_mode = 'script' if args.script else 'code'
            if code is not None:
                if args.save_code:
                    with open('generated_code.py', 'w') as file:
                        file.write(code)
                if not args.exec:
                    if input("Do you want to execute the code? (y/n): ").lower() == 'y':
                        execute_code(bard_coder, code,code_mode,os_name,coding_language)
                else:
                    execute_code(bard_coder, code,code_mode,os_name,coding_language)
                
            try:
                # Check if graph.png exists and open it using subprocess
                if os.path.isfile('graph.png'):
                    subprocess.call(['open', 'graph.png'])
                    print("graph.png exists and opened successfully")
                
                # Check if chart.png exists and open it using subprocess
                if os.path.isfile('chart.png'):
                    subprocess.call(['open', 'chart.png'])
                    print("chart.png exists and opened successfully")
                
                # Check if table.md exists and open it using subprocess
                if os.path.isfile('table.md'):
                    subprocess.call(['open', 'table.md'])
                    print("table.md exists and opened successfully")
            except Exception as exception:
                display_markdown_message(f"Error in opening files: {str(exception)}")
        
    except Exception as exception:
        stack_trace = traceback.format_exc()
        display_markdown_message(stack_trace)
        display_markdown_message(str(exception))
        

# App main entry point.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='PALM - Interpreter')
        parser.add_argument('--exec', '-e', action='store_true', help='Execute the code')
        parser.add_argument('--save_code', '-s', action='store_true', help='Save the generated code')
        parser.add_argument('--script', '-sc', action='store_true', help='Execute the shell script')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0')
        args = parser.parse_args()
        
        # Check if only the application name is passed
        if len(sys.argv) == 0 and sys.argv[0] == parser.prog:
            display_markdown_message("**Usage: python interpreter.py [options]**")
            display_markdown_message("**Options:**")
            display_markdown_message("**--exec, -e: Execute the code**")
            display_markdown_message("**--save_code: Save the generated code**")
            display_markdown_message("**--script, -sc: Execute the shell script**")
            display_markdown_message("**--version: Show the version of the program**")
            sys.exit(1)
        
        # Call the main bard.
        bard_main(args)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
