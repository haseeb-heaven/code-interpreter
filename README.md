# Open-Code-Interpreter 🚀

![cover_logo](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/logo.png?raw=true "")</br>

! [Open Interpreter] (movie.gif)

Welcome to Open-Code-Interpreter 🎉, an innovative open-source alternative to traditional Code Interpreters. This powerful tool is not just free, but it also leverages the power of HuggingFace models like Code-llama, Mistral 7b, Wizard Coder, and many more to transform your instructions into executable code.

Open-Code-Interpreter is more than just a code translator. It's a versatile tool that can execute a wide range of tasks. Whether you need to find files in your system 📂, save images from a website and convert them into a different format 🖼️, create a GIF 🎞️, edit videos 🎥, or even analyze files for data analysis and creating graphs 📊, Open-Code-Interpreter can handle it all.

After processing your instructions, Open-Code-Interpreter executes the generated code and provides you with the result. This makes it an invaluable tool for developers 💻, data scientists 🧪, and anyone who needs to quickly turn ideas into working code.

Designed with versatility in mind, Open-Code-Interpreter works seamlessly on every operating system, including Windows, MacOS, and Linux. So, no matter what platform you're on, you can take advantage of this powerful tool 💪.

Experience the future of code interpretation with Open-Code-Interpreter today! 🚀

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Contributing](#contributing)
- [Versioning](#versioning)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## 🌟 Features

- 🚀 Code Execution: Open-Code-Interpreter can execute the code generated from your instructions.
- 💾 Code Saving: It has the ability to save the generated code for future use or reference.
- 📜 Command History: It has the ability to save all the commands as history.
- 🔄 Mode Selection: It allows you to select the mode of operation. You can choose from `code` for generating code, `script` for generating shell scripts, or `command` for generating single line commands.
- 🧠 Model Selection: You can set the model for code generation. By default, it uses the `code-llama` model.
- 🌐 Language Selection: You can set the interpreter language to Python or `JavaScript`. By default, it uses `Python`.
- 👀 Code Display: It can display the generated code in the output, allowing you to review the code before execution.
- 💻 Cross-Platform: Open-Code-Interpreter works seamlessly on every operating system, including Windows, MacOS, and Linux.
- 🤝 Integration with HuggingFace: It leverages the power of HuggingFace models like Code-llama, Mistral 7b, Wizard Coder, and many more to transform your instructions into executable code.
- 🎯 Versatility: Whether you need to find files in your system, save images from a website and convert them into a different format, create a GIF, edit videos, or even analyze files for data analysis and creating graphs, Open-Code-Interpreter can handle it all.

## Installation

To get started with Open-Code-Interpreter, follow these steps:

1. Clone the repository:
git clone https://github.com/haseeb-heaven/open-code-interpreter.git
cd Open-Code-Interpreter
2. You will need a HuggingFace token. Go to [HuggingFace Tokens](https://huggingface.co/settings/tokens) and get your Access Token.
3. Save the token in a `.env` file as:
`HUGGINGFACEHUB_API_TOKEN` = "Your Access Token"

## Usage

To use Open-Code-Interpreter, use the following command options:

- Code Llama with code mode selected.
```python
python interpreter.py -m 'code-llama' -md 'code'
```
- Code Llama with command mode selected.
```python
python interpreter.py -m 'code-llama' -md 'command'
```
- Mistral with script selected
```python
python interpreter.py -m 'mistral-7b' -md 'script'
```
- Wizard Coder with code selected and display code.
```python
python interpreter.py -m 'wizard-coder' -md 'code' -dc
```
- Wizard Coder with code selected and display code and auto execution.
```python
python interpreter.py -m 'wizard-coder' -md 'code' -dc -e
```
- Code Llama with code mode selected and save code
```python
python interpreter.py -m 'code-llama' -md 'code' -s
```
- Code Llama with code mode selected and javascript selected langauge.
```python
python interpreter.py -m 'code-llama' -md 'code' -s -l 'javascript'
```

## Examples

Example of Code llama with code mode:
![code_llama_code](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/code-llama-code.png?raw=true "")</br>

Example of Code llama with command mode:
![code_llama_command](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/code-llama-command.png?raw=true "")</br>

Example of Mistral with code mode:
![mistral_code](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/mistral-code.png?raw=true "")</br>

## Contributing

If you'd like to contribute to Open-Code-Interpreter, please fork the repository and submit a pull request. We welcome all contributions and are always looking for feedback and improvements.

## Versioning

v1.0.0 - Initial release

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to HuggingFace for providing the models.
- Special thanks to the open-source community for their continuous support and contributions.