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
        self.console = Console()
        self.utility_manager = UtilityManager()

    def _read_key(self):
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
        default_choice = 'yes' if default else 'no'
        choice = self._select_option(title, ['yes', 'no'], default_choice, 'Use Up/Down arrows and Enter to choose.')
        return choice == 'yes'

    def launch(self, args):
        models = self.utility_manager.list_available_models()
        default_mode = args.mode or 'code'
        default_model = args.model or self.utility_manager.get_default_model_name()
        if default_model not in models:
            default_model = models[0]
        default_lang = args.lang or 'python'

        mode = self._select_option('Mode', ['code', 'chat', 'script', 'command', 'vision'], default_mode)
        model = self._select_option('Model', models, default_model, 'Use Up/Down arrows, Enter, or type the first letter to jump.')
        language = self._select_option('Language', ['python', 'javascript'], default_lang)

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
            upgrade=args.upgrade,
            cli=args.cli,
            tui=args.tui,
        )
