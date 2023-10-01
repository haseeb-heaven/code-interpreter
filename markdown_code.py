import subprocess
import time
from rich import print as rich_print
from rich.markdown import Markdown
from rich.rule import Rule
from rich.syntax import Syntax

def display_markdown_message(message):
    """
    Display markdown message. Works with multiline strings with lots of indentation.
    Will automatically make single line > tags beautiful.
    """

    for line in message.split("\n"):
        line = line.strip()
        if line == "":
            print("")
        elif line == "---":
            rich_print(Rule(style="white"))
        else:
            rich_print(Markdown(line))

    if "\n" not in message and message.startswith(">"):
        # Aesthetic choice. For these tags, they need a space below them
        print("")
        


def display_code(codes: list, language: str = "python"):
    try:
        code = '\n'.join(codes)
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        rich_print(syntax,end="",flush=True)
    except Exception as exception:
        print(f"An error occurred: {exception}")
        
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter

class CustomFormatter(TerminalFormatter):
    def format(self, tokensource, outfile):
        # call the parent method
        super().format(tokensource, outfile)
        # remove the trailing newline from the output file
        outfile.seek(outfile.tell() - 1)
        if outfile.read() == '\n':
            outfile.truncate()

def display_code_stream(stream):
    """
    This function prints each token in the stream as a Python syntax highlighted code block.
    :param stream: The stream of text to be printed.
    """
    try:
        code = ""
        for output in stream:
            output_code = output.token.text
            output_code = output_code.replace("```","") if output_code else output_code
            if output_code  == '\n':
                highlighted_code = Syntax(code, "python", theme="monokai", line_numbers=False,word_wrap=True)
                rich_print(highlighted_code, end="", flush=True)
                code = ""
            else:
                code += output_code + ""
            time.sleep(0.03)
    except Exception as e:
        print(f"Error while printing as markdown: {e}")
