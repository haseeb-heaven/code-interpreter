# -*- coding: utf-8 -*-*
"""
This is the main file for the Code-Interpreter.
It handles command line arguments and initializes the Interpreter.

Command line arguments:
--exec, -e: Executes the code generated from the user's instructions.
--save_code, -s: Saves the generated code.
--mode, -md: Selects the mode of operation. Choices are 'code', 'script', and 'command' and 'vision'.
--model, -m: Sets the model for code generation. Default is 'code-llama'.
--version, -v: Displays the version of the program.
--lang, -l: Sets the interpreter language. Default is 'python'.
--display_code, -dc: Displays the generated code in the output.

Author: HeavenHM
Date: 2025/01/01
"""

from libs.interpreter_lib import Interpreter
import argparse
import sys
import traceback
import warnings
from libs.markdown_code import display_markdown_message
from libs.utility_manager import UtilityManager

# The main version of the interpreter.
INTERPRETER_VERSION = "2.3.0"


def main():
	parser = argparse.ArgumentParser(description='Code - Interpreter')
	parser.add_argument('--exec', '-e', action='store_true', default=False, help='Execute the code')
	parser.add_argument('--save_code', '-s', action='store_true', default=False, help='Save the generated code')
	parser.add_argument('--mode', '-md', choices=['code', 'script', 'command', 'vision', 'chat'], help='Select the mode (`code` for generating code, `script` for generating shell scripts, `command` for generating single line commands) `vision` for generating text from images')
	parser.add_argument('--model', '-m', type=str, default='code-llama', help='Set the model for code generation. (Defaults to gpt-3.5-turbo)')
	parser.add_argument('--version', '-v', action='version', version='%(prog)s ' + INTERPRETER_VERSION)
	parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language. (Defaults to Python)')
	parser.add_argument('--display_code', '-dc', action='store_true', default=False, help='Display the code in output')
	parser.add_argument('--history', '-hi', action='store_true', default=False, help='Use history as memory')
	parser.add_argument('--upgrade', '-up', action='store_true', default=False, help='Upgrade the interpreter')
	parser.add_argument('--file', '-f', type=str, nargs='?', const='prompt.txt', default=None, help='Sets the file to read the input prompt from')
	args = parser.parse_args()

	# Check if only the application name is passed
	if len(sys.argv) <= 1:
		parser.print_help()
		return
	
	warnings.filterwarnings("ignore")  # To ignore all warnings

	# Upgrade the interpreter if the --upgrade flag is passed.
	if args.upgrade:
		UtilityManager.upgrade_interpreter()
		return
	
	# Create an instance of the Interpreter class and call the main method.
	interpreter = Interpreter(args)
	interpreter.interpreter_main(INTERPRETER_VERSION)


if __name__ == "__main__":
	try:
		main()
	except SystemExit:
		pass  # Ignore the SystemExit exception caused by --version argument
	except Exception as exception:
		# Print a meaningful error message if the interpreter is not setup properly.
		if ".env file" in str(exception):
			display_markdown_message("Interpreter is not setup properly. Please follow these steps \
			to setup the interpreter:\n\
			1. Create a .env file in the root directory of the project.\n\
			2. Add the following line to the .env file:\n\
			GEMINI_API_KEY=<your api key>\n\
			OPENAI_API_KEY=<your api key>\n\
			ANTHROPIC_API_KEY=<your api key>\n\
			3. Replace <your api key> with your OpenAI/Gemini API key.\n\
			4. Run the interpreter again.")
			
		else:
			display_markdown_message(f"An error occurred interpreter main: {exception}")
			traceback.print_exc()
