# -*- coding: utf-8 -*-*
"""
This is the main file for the Code-Interpreter.
It handles command line arguments and initializes the Interpreter.

Command line arguments:
--exec, -e: Executes the code generated from the user's instructions.
--save_code, -s: Saves the generated code.
--mode, -md: Selects the mode of operation. Choices are 'code', 'script', and 'command' and 'vision'.
--model, -m: Sets the model for code generation.
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
from libs.terminal_ui import TerminalUI
from libs.utility_manager import UtilityManager

# The main version of the interpreter.
INTERPRETER_VERSION = "3.1.1"


def build_parser():
    parser = argparse.ArgumentParser(description='Code - Interpreter')
    parser.add_argument('--exec', '-e', action='store_true', default=False, help='Execute the code')
    parser.add_argument('--save_code', '-s', action='store_true', default=False, help='Save the generated code')
    parser.add_argument('--mode', '-md', choices=['code', 'script', 'command', 'vision', 'chat'], help='Select the mode (`code` for generating code, `script` for generating shell scripts, `command` for generating single line commands) `vision` for generating text from images')
    parser.add_argument('--model', '-m', type=str, default=None, help='Set the model for code generation. (Defaults to the best configured local provider)')
    parser.add_argument('--version', '-v', action='version', version='%(prog)s ' + INTERPRETER_VERSION)
    parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language. (Defaults to Python)')
    parser.add_argument('--display_code', '-dc', action='store_true', default=False, help='Display the generated code in output')
    parser.add_argument('--history', '-hi', action='store_true', default=False, help='Use history as memory')
    parser.add_argument('--upgrade', '-up', action='store_true', default=False, help='Upgrade the interpreter')
    parser.add_argument('--file', '-f', type=str, nargs='?', const='prompt.txt', default=None, help='Sets the file to read the input prompt from')
    parser.add_argument("--unsafe", action="store_true", help="Allow unsafe execution (write/delete enabled)")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--cli', action='store_true', default=False, help='Launch the classic interactive CLI')
    mode_group.add_argument('--tui', action='store_true', default=False, help='Launch the selector-based terminal UI')
    return parser


def _get_default_model():
    return UtilityManager.get_default_model_name()


def prepare_args(args, argv):
    no_runtime_args = len(argv) <= 1
    if no_runtime_args and not args.cli and not args.tui:
        args.tui = True

    if args.tui:
        return TerminalUI().launch(args)

    if not args.mode:
        args.mode = 'code'
    if not args.model:
        args.model = _get_default_model()
    args.cli = True
    return args


def main(argv=None):
    argv = argv or sys.argv
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    warnings.filterwarnings("ignore")

    if args.upgrade:
        UtilityManager.upgrade_interpreter()
        return

    args = prepare_args(args, argv)

    interpreter = Interpreter(args)
    interpreter.interpreter_main(INTERPRETER_VERSION)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as exception:
        if ".env file" in str(exception):
            display_markdown_message("Interpreter is not setup properly. Please follow these steps \
            to setup the interpreter:\n\
            1. Create a .env file in the root directory of the project.\n\
            2. Add the required API keys to the .env file or copy them from .env.example.\n\
            3. Run the interpreter again.")
        else:
            display_markdown_message(f"An error occurred interpreter main: {exception}")
            traceback.print_exc()
