import pytest
from libs.terminal_ui import TerminalUI

def test_tui_init():
    tui = TerminalUI()
    assert tui is not None
