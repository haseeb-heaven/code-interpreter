# -*- coding: utf-8 -*-
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
--sandbox / --no-sandbox: Enable or disable sandbox mode (default: sandbox ON).

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
INTERPRETER_VERSION = "3.3.0"


def build_parser():
	parser = argparse.ArgumentParser(description='Code - Interpreter')
	parser.add_argument('--exec', '-e', action='store_true', default=False, help='Execute the code')
	parser.add_argument('--save_code', '-s', action='store_true', default=False, help='Save the generated code')
	parser.add_argument('--mode', '-md', choices=['code', 'script', 'command', 'vision', 'chat', 'generate', 'project'], help='Select the mode (`code`/`script`/`command`/`vision`/`chat`, or `generate`/`project` for code-gen without execution)')
	parser.add_argument('--model', '-m', type=str, default=None, help='Set the model for code generation. (Defaults to the best configured local provider)')
	parser.add_argument(
		'--task', '-t',
		type=str,
		default=None,
		help='One-shot task text for --mode generate|project (or use -f prompt file)',
	)
	parser.add_argument(
		'--output', '-o',
		type=str,
		default=None,
		help='Output file (--mode generate) or directory (--mode project)',
	)
	parser.add_argument('--version', '-v', action='version', version='%(prog)s ' + INTERPRETER_VERSION)
	parser.add_argument('--lang', '-l', type=str, default='python', help='Set the interpreter language. (Defaults to Python)')
	parser.add_argument('--display_code', '-dc', action='store_true', default=False, help='Display the generated code in output')
	parser.add_argument('--history', '-hi', action='store_true', default=False, help='Use history as memory')
	parser.add_argument('--upgrade', '-up', action='store_true', default=False, help='Upgrade the interpreter')
	parser.add_argument('--file', '-f', type=str, nargs='?', const='prompt.txt', default=None, help='Sets the file to read the input prompt from')
	parser.add_argument('--agentic', action='store_true', default=False, help='Use ReAct agentic workflow (Coder, Executor, Reviewer, Debugger)')
	parser.add_argument(
		'--gemini-style',
		action='store_true',
		default=False,
		help='Gemini-CLI-inspired agentic REPL: ReAct loop, free-model preference, CLI banner (/free, /model)',
	)
	parser.add_argument(
		'--free',
		action='store_true',
		default=False,
		help='Prefer a free/cheap model from configs/free/catalog.json when -m is omitted',
	)
	parser.add_argument(
		'--list-free',
		action='store_true',
		default=False,
		help='List curated free/cheap LLM presets and exit',
	)

	# Sandbox control: --sandbox (default ON) / --no-sandbox (unsafe, disables sandbox+timers)
	sandbox_group = parser.add_mutually_exclusive_group()

	sandbox_group.add_argument(
	    '--sandbox',
	    dest='sandbox',
	    action='store_true',
	    help='Enable sandbox mode (default: ON)'
	)

	sandbox_group.add_argument(
	    '--no-sandbox',
	    dest='sandbox',
	    action='store_false',
	    help='Disable sandbox (UNSAFE)'
	)

	# Set default to sandbox mode ON
	parser.set_defaults(sandbox=True)

	# Legacy --unsafe flag kept for backwards compatibility (maps to --no-sandbox)
	parser.add_argument(
		"--unsafe",
		action='store_true',
		default=False,
		help=argparse.SUPPRESS  # hidden; use --no-sandbox instead
	)

	mode_group = parser.add_mutually_exclusive_group()
	mode_group.add_argument('--cli', action='store_true', default=False, help='Launch the classic interactive CLI')
	mode_group.add_argument('--tui', action='store_true', default=False, help='Launch the selector-based terminal UI')
	parser.add_argument(
		'--agent',
		action='store_true',
		default=False,
		help='Run tasks through the multi-agent pipeline (IntentRouter -> Planner -> SafetyGuard -> Executor -> Repairer -> Verifier -> Reviewer)',
	)
	parser.add_argument(
		'-y', '--yes',
		action='store_true',
		default=False,
		help='Non-interactive mode: auto-confirm prompts, run file task once, then exit (CI/script friendly)',
	)
	parser.add_argument(
		'--yolo',
		action='store_true',
		default=False,
		help='Fully autonomous tool loop — execute FS/shell tools without approval prompts. Use with caution.',
	)
	parser.add_argument(
		'--mcp-server',
		nargs=argparse.REMAINDER,
		metavar='CMD',
		default=None,
		help=(
			'Launch an MCP server (stdio) and register its tools. '
			'Put this flag last so args like npx -y ... are not parsed as CLI flags. '
			'E.g.: --mcp-server npx -y @modelcontextprotocol/server-filesystem .'
		),
	)
	stream_group = parser.add_mutually_exclusive_group()
	stream_group.add_argument(
		'--stream',
		dest='stream',
		action='store_true',
		help='Stream tokens as they are generated (default: on for --gemini-style).',
	)
	stream_group.add_argument(
		'--no-stream',
		dest='stream',
		action='store_false',
		help='Disable token streaming; wait for the full LLM response.',
	)
	parser.set_defaults(stream=True)
	parser.add_argument(
		'--image',
		nargs='+',
		metavar='PATH_OR_URL',
		default=None,
		help='One or more image paths or URLs to include with the prompt (multimodal / vision).',
	)
	parser.add_argument(
		'--search',
		action='store_true',
		default=False,
		help='Enable web search tool (DuckDuckGo by default; no API key needed).',
	)
	parser.add_argument(
		'--search-provider',
		choices=['duckduckgo', 'tavily', 'serper'],
		default='duckduckgo',
		help='Search provider to use. Default: duckduckgo (free, no API key).',
	)
	parser.add_argument(
		'--search-api-key',
		metavar='KEY',
		default=None,
		help='API key for Tavily or Serper search providers (or set TAVILY_API_KEY / SERPER_API_KEY).',
	)
	return parser


def _get_default_model():
	return UtilityManager.get_default_model_name()


def prepare_args(args, argv):
	# --unsafe is a legacy alias for --no-sandbox
	if getattr(args, 'unsafe', False):
		args.sandbox = False

	# sandbox=False means unsafe execution
	args.unsafe = not args.sandbox

	# Gemini-CLI-style: agentic REPL + free-model preference + classic CLI (not TUI)
	if getattr(args, 'gemini_style', False):
		args.agentic = True
		args.free = True
		args.cli = True
		args.tui = False
		args.stream = True  # Gemini-CLI parity: always stream tokens

	# Multimodal --image implies classic CLI (not TUI)
	if getattr(args, 'image', None):
		args.cli = True
		args.tui = False

	# Auto-enable --yes in CI environments so scripted runs never hang on input()
	import os
	if not getattr(args, 'yes', False):
		ci = os.environ.get('CI', '').lower() in ('1', 'true', 'yes')
		auto = os.environ.get('INTERPRETER_YES', '').lower() in ('1', 'true', 'yes')
		if ci or auto:
			args.yes = True

	# Autonomous tool loop / MCP: classic CLI path (not TUI)
	if getattr(args, 'yolo', False) or getattr(args, 'mcp_server', None):
		args.cli = True
		args.tui = False
		# Non-interactive / CI: skip tool approval prompts
		if getattr(args, 'yes', False):
			args.yolo = True

	# Codegen modes never launch TUI; require CLI one-shot
	if getattr(args, 'mode', None) in ('generate', 'project'):
		args.cli = True
		args.tui = False

	no_runtime_args = len(argv) <= 1
	if no_runtime_args and not args.cli and not args.tui:
		args.tui = True
	if args.tui:
		return TerminalUI().launch(args)
	if not args.mode:
		args.mode = 'code'
	if not args.model:
		if getattr(args, 'free', False):
			from libs.free_llms import resolve_free_model

			picked = resolve_free_model(prefer_free=True)
			args.model = picked or _get_default_model()
		else:
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
	if getattr(args, 'list_free', False):
		from libs.free_llms import FreeLLMCatalog

		print(FreeLLMCatalog.load().format_table())
		return
	args = prepare_args(args, argv)
	# Code generation modes — write artifacts only, never execute (#212)
	if getattr(args, 'mode', None) in ('generate', 'project'):
		from libs.code_generator import run_codegen_cli

		# Interpreter boots model config / .env; codegen reuses it then exits.
		interpreter = Interpreter(args)
		run_codegen_cli(args, interpreter=interpreter)
		return

	interpreter = Interpreter(args)
	if getattr(args, 'yolo', False) or getattr(args, 'mcp_server', None):
		interpreter.interpreter_auto_main()
	elif getattr(args, 'agentic', False):
		interpreter.interpreter_agentic_main()
	else:
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
