import time
from rich import print as rich_print
from rich.markdown import Markdown
from rich.rule import Rule
from rich.syntax import Syntax
from pygments.formatters import TerminalFormatter

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
        

def display_code(code: list, language: str = "python"):
    try:
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        rich_print(syntax,end="",flush=True)
    except Exception as exception:
        print(f"An error occurred: {exception}")
        

class CustomFormatter(TerminalFormatter):
    def format(self, tokensource, outfile):
        # call the parent method
        super().format(tokensource, outfile)
        # remove the trailing newline from the output file
        outfile.seek(outfile.tell() - 1)
        if outfile.read() == '\n':
            outfile.truncate()

from rich.console import Console

def display_code_stream(stream):
    """
    This function prints each token in the stream as a Python syntax highlighted code block.
    :param stream: The stream of text to be printed.
    """
    try:
        code = ""
        console = Console(record=True)  # Create a Console object that records print calls

        for output in stream:
            output_code = output.token.text
            output_code = output_code.replace("```","") if output_code else output_code
            output_code = output_code.replace("</s>","") if output_code else output_code
            if output_code  == '\n':
                highlighted_code = Syntax(code, "python", theme="monokai", line_numbers=False,word_wrap=True)
                console.print(highlighted_code)  # Print to the console object
                code = ""
            else:
                code += output_code + ""
            time.sleep(0.03)

        # Check if there is any remaining code that hasn't been printed
        if code:
            highlighted_code = Syntax(code, "python", theme="monokai", line_numbers=False,word_wrap=True)
            console.print(highlighted_code)  # Print to the console object
            code = ""
            
        return console.export_text().strip()  # Return the recorded text
    except Exception as exception:
        print(f"Error while printing as markdown: {exception}")