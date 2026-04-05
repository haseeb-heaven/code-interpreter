from argparse import Namespace
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from libs.utility_manager import UtilityManager


class TerminalUI:
    def __init__(self):
        """
        Initialize the TerminalUI by creating a Rich Console for rendering and a UtilityManager for terminal utilities.
        
        Attributes:
            console: Rich Console instance used for rendering UI elements.
            utility_manager: UtilityManager instance used for screen management and model utilities.
        """
        self.console = Console()
        self.utility_manager = UtilityManager()

    def _read_key(self):
        """
        Read a single keypress from stdin and normalize special keys to logical names.
        
        On Windows, reads a wide character via msvcrt and decodes extended key sequences into
        arrow directions. On Unix-like systems, puts stdin into raw mode, reads one (or
        few) byte(s) to decode ANSI escape sequences for arrows, and ensures terminal
        settings are restored before returning.
        
        Returns:
            str: One of the normalized tokens `'up'`, `'down'`, `'left'`, `'right'`, `'enter'`,
            or `'escape'` for those special keys; otherwise the single-character string
            that was pressed.
        """
        if os.name == 'nt':
            import msvcrt
            key = msvcrt.getwch()
            if key in ('\x00', '\xe0'):
                extended = msvcrt.getwch()
                mapping = {'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right'}
                return mapping.get(extended, extended)
            if key == '\r':
                return 'enter'
            if key == '\x1b':
                return 'escape'
            return key

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
            if key == '\x1b':
                next_chars = sys.stdin.read(2)
                mapping = {'[A': 'up', '[B': 'down', '[D': 'left', '[C': 'right'}
                return mapping.get(next_chars, 'escape')
            if key in ('\r', '\n'):
                return 'enter'
            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _render_selector(self, title, options, selected_index, help_text, default):
        """
        Render a scrollable terminal selector UI and display the current selection.
        
        Renders an interactive-looking selector using the console: clears the screen, prints the title, a table of visible option rows with a marker for the current selection, a footer/help panel, and a "Selected" line showing the option at the current index.
        
        Parameters:
            title (str): Heading displayed above the options.
            options (Sequence[str]): List of option labels to display.
            selected_index (int): Index of the option to mark as selected and center in the visible window when possible.
            help_text (Optional[str]): Text shown in the footer panel; when falsy, a default usage hint is shown.
            default (Optional[str]): Option label to annotate with " (default)" when present among the visible items.
        """
        self.utility_manager.clear_screen()
        visible_rows = max(8, min(14, self.console.size.height - 10))
        start_index = max(0, selected_index - visible_rows // 2)
        end_index = min(len(options), start_index + visible_rows)
        start_index = max(0, end_index - visible_rows)

        table = Table(show_header=True, header_style='bold cyan')
        table.add_column('', width=2)
        table.add_column('Value', overflow='fold')

        for index in range(start_index, end_index):
            option = options[index]
            marker = '>' if index == selected_index else ' '
            label = option
            if option == default:
                label += ' (default)'
            style = 'bold green' if index == selected_index else ''
            table.add_row(marker, label, style=style)

        footer = help_text or 'Use Up/Down arrows and Enter to select.'
        self.console.print(Panel.fit(footer, title='Interpreter TUI', border_style='green'))
        self.console.print(f"[bold cyan]{title}[/bold cyan]")
        self.console.print(table)
        self.console.print(f'Selected: [bold]{options[selected_index]}[/bold]')

    def _select_option(self, title, options, default, help_text=None):
        """
        Present a selectable list of options to the user and return the chosen option.
        
        If stdin is not a TTY, prompts once using the provided title and returns
        an exact or case-insensitive match from `options`, falling back to a valid
        default. If stdin is a TTY, displays an interactive selector that accepts
        Up/Down (or k/j), single-character prefix selection, Enter to confirm, and
        Escape to cancel.
        
        Parameters:
            title (str): Prompt title displayed to the user.
            options (list[str]): Non-empty list of option strings to choose from.
            default (str): Default option to pre-select or fall back to if no match.
            help_text (str | None): Optional help text shown in the selector footer.
        
        Returns:
            str: The selected option (one of the entries from `options`).
        
        Raises:
            KeyboardInterrupt: If the user cancels the selection (Escape) in interactive mode.
        """
        if not sys.stdin.isatty():
            default_choice = default if default in options else options[0]
            answer = Prompt.ask(f"{title}", default=default_choice).strip()
            if answer in options:
                return answer
            for option in options:
                if option.lower() == answer.lower():
                    return option
            return default_choice

        try:
            selected_index = options.index(default)
        except ValueError:
            selected_index = 0

        while True:
            self._render_selector(title, options, selected_index, help_text, default)
            key = self._read_key()

            if key in ('up', 'k'):
                selected_index = (selected_index - 1) % len(options)
            elif key in ('down', 'j'):
                selected_index = (selected_index + 1) % len(options)
            elif key == 'enter':
                return options[selected_index]
            elif key == 'escape':
                raise KeyboardInterrupt('Selection cancelled by user.')
            elif isinstance(key, str) and len(key) == 1:
                lowered = key.lower()
                for index, option in enumerate(options):
                    if option.lower().startswith(lowered):
                        selected_index = index
                        break

    def _select_boolean(self, title, default=False):
        """
        Prompt the user to choose between 'yes' and 'no' and return the selection as a boolean.
        
        Parameters:
            title (str): The prompt title displayed to the user.
            default (bool): The default selection when no explicit choice is made.
        
        Returns:
            bool: `True` if 'yes' is selected, `False` otherwise.
        """
        default_choice = 'yes' if default else 'no'
        choice = self._select_option(title, ['yes', 'no'], default_choice, 'Use Up/Down arrows and Enter to choose.')
        return choice == 'yes'

    def select_mode(self, default_mode='code'):
        """
        Prompt the user to choose an interpreter mode.
        
        Parameters:
            default_mode (str): Mode to preselect in the chooser; if it is not a valid choice, the first available mode is used.
        
        Returns:
            str: The selected mode, one of 'code', 'chat', 'script', 'command', or 'vision'.
        """
        return self._select_option('Mode', ['code', 'chat', 'script', 'command', 'vision'], default_mode)

    def select_model(self, default_model=None):
        """
        Prompt the user to choose a model from the list of available models.
        
        Parameters:
            default_model (str | None): Preferred model name to preselect. If None, the utility manager's default is used; if that default is not in the available list, the first available model is used.
        
        Returns:
            str: The chosen model name from the available models.
        """
        models = self.utility_manager.list_available_models()
        default_model = default_model or self.utility_manager.get_default_model_name()
        if default_model not in models:
            default_model = models[0]
        return self._select_option('Model', models, default_model, 'Use Up/Down arrows, Enter, or type the first letter to jump.')

    def select_language(self, default_lang='python'):
        """
        Prompt the user to choose a programming language from available options.
        
        Parameters:
            default_lang (str): Language to pre-select or fall back to if the user provides no valid selection.
        
        Returns:
            str: The selected language, either 'python' or 'javascript'.
        """
        return self._select_option('Language', ['python', 'javascript'], default_lang)

    def select_boolean(self, title, default=False):
        """
        Prompt the user to choose between "yes" and "no".
        
        Parameters:
            title (str): The prompt title shown to the user.
            default (bool): The default choice used when no explicit selection is made.
        
        Returns:
            bool: `True` if the user selects "yes", `False` otherwise.
        """
        return self._select_boolean(title, default=default)

    def interactive_settings(self, interpreter):
        """
        Prompt the user for interpreter settings using interactive selectors and return the chosen configuration.
        
        Parameters:
            interpreter: An interpreter-like object used to read current defaults. Recognized attributes (if present) are:
                - INTERPRETER_MODEL_LABEL or INTERPRETER_MODEL: default model name
                - INTERPRETER_MODE: default mode (defaults to "code")
                - INTERPRETER_LANGUAGE: default language (defaults to "python")
                - DISPLAY_CODE: default for displaying generated code (bool)
                - EXECUTE_CODE: default for auto-executing code (bool)
                - SAVE_CODE: default for saving generated output (bool)
                - INTERPRETER_HISTORY: default for enabling history (bool)
        
        Returns:
            dict: A mapping with the selected settings:
                - "mode" (str): selected interpreter mode
                - "model" (str): selected model name
                - "language" (str): selected language
                - "display_code" (bool): whether to display generated code automatically
                - "execute_code" (bool): whether to execute generated code automatically
                - "save_code" (bool): whether to save generated output automatically
                - "history" (bool): whether history memory is enabled
        """
        current_model = getattr(interpreter, "INTERPRETER_MODEL_LABEL", None) or getattr(interpreter, "INTERPRETER_MODEL", None)
        current_mode = getattr(interpreter, "INTERPRETER_MODE", "code")
        current_lang = getattr(interpreter, "INTERPRETER_LANGUAGE", "python")

        mode = self.select_mode(current_mode)
        model = self.select_model(current_model)
        language = self.select_language(current_lang)
        display_code = self.select_boolean('Display generated code automatically?', default=getattr(interpreter, "DISPLAY_CODE", False))
        execute_code = self.select_boolean('Execute generated code automatically?', default=getattr(interpreter, "EXECUTE_CODE", False))
        save_code = self.select_boolean('Save generated output automatically?', default=getattr(interpreter, "SAVE_CODE", False))
        history = self.select_boolean('Enable history memory?', default=getattr(interpreter, "INTERPRETER_HISTORY", False))

        return {
            "mode": mode,
            "model": model,
            "language": language,
            "display_code": display_code,
            "execute_code": execute_code,
            "save_code": save_code,
            "history": history,
        }

    def launch(self, args):
        """
        Present interactive prompts for interpreter settings (mode, model, language and related booleans) and return a resolved argparse.Namespace.
        
        Prompts the user for mode, model, and language (using provided CLI values as defaults). For appropriate modes, prompts for booleans controlling display of generated code, automatic execution, saving output, and history when those flags are not supplied on the CLI. Clears the terminal and renders a summary panel of the chosen configuration before requesting any additional boolean choices.
        
        Parameters:
            args (argparse.Namespace): CLI arguments and flags. Expected attributes:
                - mode, model, lang: optional initial choices for mode, model, and language.
                - display_code, exec, save_code, history: optional boolean flags that, if falsy, may trigger interactive prompts.
                - file: path or identifier to include in the returned namespace.
                - unsafe (optional): passed through; defaults to False if missing.
                - upgrade, cli, tui: passthrough flags included in the returned namespace.
        
        Returns:
            argparse.Namespace: Namespace containing the resolved settings with keys:
                exec, save_code, mode, model, display_code, lang, file, history, unsafe, upgrade, cli, tui.
        """
        mode = self.select_mode(args.mode or 'code')
        model = self.select_model(args.model or self.utility_manager.get_default_model_name())
        language = self.select_language(args.lang or 'python')

        self.utility_manager.clear_screen()
        self.console.print(
            Panel.fit(
                f"Mode: [bold]{mode}[/bold] | Model: [bold]{model}[/bold] | Language: [bold]{language}[/bold]",
                title='Interpreter Session',
                border_style='blue',
            )
        )

        display_code = args.display_code
        if mode in ['code', 'script', 'command'] and not display_code:
            display_code = self._select_boolean('Display generated code automatically?', default=True)

        execute_code = args.exec
        if mode == 'code' and not execute_code:
            execute_code = self._select_boolean('Execute generated code automatically?', default=False)

        save_code = args.save_code
        if mode in ['code', 'script', 'command'] and not save_code:
            save_code = self._select_boolean('Save generated output automatically?', default=False)

        history = args.history
        if not history:
            history = self._select_boolean('Enable history memory?', default=False)

        return Namespace(
            exec=execute_code,
            save_code=save_code,
            mode=mode,
            model=model,
            display_code=display_code,
            lang=language,
            file=args.file,
            history=history,
            unsafe=getattr(args, "unsafe", False),
            upgrade=args.upgrade,
            cli=args.cli,
            tui=args.tui,
        )
