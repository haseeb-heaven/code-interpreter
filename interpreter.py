from libs.interpreter_lib import Interpreter
import argparse
import sys
import traceback

def main():
        parser = argparse.ArgumentParser(description='Code - Interpreter')
        parser.add_argument('--exec', '-e', action='store_true', help='Execute the code')
        parser.add_argument('--save_code', '-s', action='store_true', help='Save the generated code')
        parser.add_argument('--mode', '-md', choices=['code', 'script', 'command'], help='Select the mode (`code` for generating code, `script` for generating shell scripts, `command` for generating single line commands)')
        parser.add_argument('--model', '-m', type=str, default='code-llama', help='Set the model for code generation. (Defaults to gpt-3.5-turbo)')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.4')
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
    except SystemExit:
        pass  # Ignore the SystemExit exception caused by --version argument
    except:
        traceback.print_exc()