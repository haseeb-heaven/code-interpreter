![Interpreter](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/movie.gif?raw=true)

### **Hosting and Spaces:**
[![Colab](https://img.shields.io/badge/Google-Colab-blue)](https://colab.research.google.com/drive/1jGg-NavH8t4W2UVs8MyVMv8bs49qggfA?usp=sharing)
[![Replit](https://img.shields.io/badge/Replit-IDE-blue)](https://replit.com/@HaseebMir/open-code-interpreter)
[![PyPi](https://img.shields.io/badge/PyPi-Package-blue)](https://pypi.org/project/open-code-interpreter/)
[![Building](https://github.com/haseeb-heaven/Open-Code-Interpreter/actions/workflows/python-app.yml/badge.svg)](https://github.com/haseeb-heaven/Open-Code-Interpreter/actions/workflows/python-app.yml)

### **Support Project:**
<a href="https://www.buymeacoffee.com/haseebheaven">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=haseebheaven&button_colour=40DCA5&font_colour=ffffff&font_family=Cookie&outline_colour=000000&coffee_colour=FFDD00" width="200" height="50" />
</a>
<a href="https://ko-fi.com/heavenhm">
    <img src="https://img.shields.io/badge/KoFi-ffdd00?style=for-the-badge&logo=Ko-fi&logoColor=orange" width="200" height="50" />
</a>

**Welcome to Code-Interpreter 🎉,** an innovative open-source and free alternative to traditional Code Interpreters. This powerful tool leverages **OpenAI**, **Gemini**, **Groq**, **Claude**, **DeepSeek**, **NVIDIA NIM**, **Z AI**, **Browser Use**, and **HuggingFace** models to transform your instructions into executable code for **free** and **safe** use, and includes **Vision Models** for image processing.

**Code-Interpreter** is more than just a code generator. It's a versatile tool that can execute a wide range of tasks. Whether you need to find files in your system 📂, save images from a website and convert them into a different format 🖼️, create a GIF 🎞️, edit videos 🎥, or even analyze files for data analysis and creating graphs 📊, Code-Interpreter can handle it all.

After processing your instructions, **Code-Interpreter** executes the generated code and provides you with the result. This makes it an invaluable tool for developers 💻, data scientists 🧪, and anyone who needs to quickly turn ideas into working code and now with **Vision Models** it can also process images and videos.

Designed with versatility in mind, **Code-Interpreter** works seamlessly on every operating system, including _Windows, MacOS, and Linux_. So, no matter what platform you're on, you can take advantage of this powerful tool 💪.

**Experience the future of code interpretation with Code-Interpreter today! 🚀**

## **Why this is Unique Interpreter?**

The distinguishing feature of this interpreter, as compared to others, is its **commitment to remain free 🆓**. It does not require any model to download or follow to **tedious processes** or methods for execution. It is designed to be **simple** and **free** for all users and works on all major OS **_Windows,Linux,MacOS_**

## **Future Plans:**
- ~~🎯 We plan to integrate **GPT 3.5** models.~~ *🎯 We have added support for **GPT 3.5** models*.
- 🔗 ~~We plan to provide API Base change using [**LiteLLM**](https://litellm.ai/)~~. Added Support for [**LiteLLM**](https://litellm.ai/)
- 🤖 More **Hugging Face** models with free-tier.
- 💻 Support for more **Operating Systems**.
- 📝 Support for **Multi-Modal** for _Text_ and _Vision_.
- 📊 Support for **Google** and **OpenAI** Vision Models.
- 💻 ~~Support for **Local** models via **LM Studio**.~~
- 🔗 Support for **Multi-Modal** models from Anthropic AI.

## **Table of Contents**
- [Features](#🌟-features)
- [Installation](#📥-installation)
- [Usage](#️🛠️-usage)
- [Examples](#📖-examples)
- [Settings](#️⚙️-settings)
- [Contributing](#🤝-contributing)
- [Versioning](#📌-versioning)
- [License](#📜-license)
- [Acknowledgments](#🙏-acknowledgments)

## 📥 **Installation**

## Installtion with Python package manager.
To install Code-Interpreter, run the following command:</br>

```bash
pip install open-code-interpreter
```
- To run the interpreter with Python:</br>
```bash
interpreter -m 'gpt-4o' -md 'code' -dc
```
- Make sure you install required packages before running the interpreter.</br>
- And you have API keys setup in the `.env` file.</br>

## Installtion with Git
To get started with Code-Interpreter, follow these steps:</br>

1. Clone the repository:</br>
```git
git clone https://github.com/haseeb-heaven/code-interpreter.git
cd code-interpreter
```
2. Install the required packages:</br>
```bash
pip install -r requirements.txt
```
3. Setup the Keys required.
4. Copy the example environment file and add the keys you plan to use:</br>
```bash
copy .env.example .env
```

## API Key setup for All models.

Follow the steps below to obtain and set up the API keys for each service:

1. **Obtain the API keys:**
    - HuggingFace: Visit [HuggingFace Tokens](https://huggingface.co/settings/tokens) and get your Access Token.
    - Google Gemini: Visit [Google AI Studio](https://makersuite.google.com/app/apikey) and click on the **Create API Key** button.
    - OpenAI: Visit [OpenAI Dashboard](https://platform.openai.com/account/api-keys), sign up or log in, navigate to the API section in your account dashboard, and click on the **Create New Key** button.
    - Groq AI: Obtain access [here](https://wow.groq.com), then visit [Groq AI Console](https://console.groq.com/keys), sign up or log in, navigate to the API section in your account, and click on the **Create API Key** button.
    - Anthropic AI: Obtain access [here](https://www.anthropic.com/earlyaccess), then visit [Anthropic AI Console](https://console.anthropic.com/settings/keys), sign up or log in, navigate to the API Keys section in your account, and click on the **Create Key** button.
    - NVIDIA API Catalog: Visit [NVIDIA Build](https://build.nvidia.com/), create a key, and use `NVIDIA_API_KEY`.
    - Z AI: Visit [Z AI Docs](https://docs.z.ai/) and use `Z_AI_API_KEY`.
    - OpenRouter: Visit [OpenRouter Keys](https://openrouter.ai/settings/keys) and use `OPENROUTER_API_KEY`.
    - Browser Use: Visit [Browser Use Docs](https://docs.browser-use.com/) and use `BROWSER_USE_API_KEY`.

2. **Save the API keys:**
    - Create a `.env` file in your project root directory.
    - Open the `.env` file and add the following lines, replacing `Your API Key` with the respective keys:

```bash
export HUGGINGFACE_API_KEY="Your HuggingFace API Key"
export GEMINI_API_KEY="Your Google Gemini API Key"
export OPENAI_API_KEY="Your OpenAI API Key"
export GROQ_API_KEY="Your Groq API Key"
export ANTHROPIC_API_KEY="Your Anthropic API Key"
export DEEPSEEK_API_KEY="Your Deepseek API Key"
export NVIDIA_API_KEY="Your NVIDIA API Key"
export Z_AI_API_KEY="Your Z AI API Key"
export OPENROUTER_API_KEY="Your OpenRouter API Key"
export BROWSER_USE_API_KEY="Your Browser Use API Key"
```

# Offline models setup.</br>
This Interpreter supports offline models via **LM Studio** and **OLlaMa** so to download it from [LM-Studio](https://lmstudio.ai/) and [Ollama](https://ollama.com/) follow the steps below.
- Download any model from **LM Studio** like _Phi-2,Code-Llama,Mistral_.
- Then in the app go to **Local Server** option and select the model.
- Start the server and copy the **URL**. (LM-Studio will provide you with the URL).
- Run command `ollama serve` and copy the **URL**. (OLlaMa will provide you with the URL).
- Open config file `configs/local-model.config` and paste the **URL** in the `api_base` field.
- Now you can use the model with the interpreter set the model name to `local-model` and run the interpreter.</br>

4. Run the interpreter with Python:</br>
### Running with Python.
```bash
python interpreter.py -md 'code' -m 'gpt-4o' -dc 
```

5. Run the interpreter directly:</br>
### Running Interpreter without Python (Executable MacOs/Linux only).
```bash
./interpreter -md 'code' -m 'gpt-4o' -dc 
```

## 🌟 **Features**

- 🚀 Code Execution: Code-Interpreter can execute the code generated from your instructions.

- 💾 Code Save/Update: It has the ability to save the generated code for future use and 
 edit the code if needed on the go using **advanced editor**.

- 📡 Offline models: It has the ability to use **offline models** for code generation using **LM Studio**.

- 📜 Command History: It has the ability to save all the commands as history.

- 📜 Command Mode: Commands entered with '/' are executed as commands like `/execute` or `/edit`.

- 🔄 Mode Selection: It allows you to select the mode of operation. You can choose from `code` for generating code, `script` for generating shell scripts, or `command` for generating single line commands.

- 🧠 Model Selection: You can set the model for code generation. By default, it uses the `code-llama` model.

- 🌐 Language Selection: You can set the interpreter language to Python or `JavaScript`. By default, it uses `Python`.

- 👀 Code Display: It can display the generated code in the output, allowing you to review the code before execution.

- 🛡️ Safe Sandbox Execution: Generated code, commands, and scripts now run inside an isolated subprocess environment with stripped secrets, a temporary working directory, execution timeout, and dangerous-operation blocking by default.

- 🧠 Self-Repair Loop: Failed executions can trigger a bounded ReACT-style repair pass that regenerates a safer fix and retries with a circuit breaker.

- 💻 Cross-Platform: Code-Interpreter works seamlessly on every operating system, including Windows, MacOS, and Linux.

- 🤝 Integration with HuggingFace: It leverages the power of HuggingFace models like Code-llama, Mistral 7b, Wizard Coder, and many more to transform your instructions into executable code.

- 🎯 Versatility: Whether you need to find files in your system, save images from a website and convert them into a different format, create a GIF, edit videos, or even analyze files for data analysis and creating graphs, Code-Interpreter can handle it all.

## 🛠️ **Usage**

To use Code-Interpreter, use the following command options:

- List of all **programming languages** are: </br>
    - `python` - Python programming language.
    - `javascript` - JavaScript programming language.

- List of all **modes** are: </br>
    - `code` - Generates code from your instructions.
    - `script` - Generates shell scripts from your instructions.
    - `command` - Generates single line commands from your instructions.
    -  `vision` - Generates description of image or video.
    - `chat` - Chat with your files and data.

- List of all **models** are (**Contribute - MORE**): </br>
    - **OpenAI stable-first (2026)**
    - `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5-mini`, `o4-mini`, `o3`, `o3-mini`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1-mini`.
    - **OpenAI legacy aliases**
    - `gpt-4` -> `gpt-4.1`, `gpt-3.5-turbo` -> `gpt-4o-mini`, `o1-preview` -> `o1`.
    - **Gemini stable-first (2026)**
    - `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`.
    - **Gemini preview (optional)**
    - `gemini-3.1-pro-preview`, `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`.
    - **Gemini legacy aliases**
    - `gemini-pro`, `gemini-1.5-pro`, `gemini-1.5-flash` are remapped to Gemini 2.5 stable models.
    - **Anthropic stable-first (2026)**
    - `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5`.
    - **Anthropic legacy aliases**
    - `claude-2`, `claude-2.1`, `claude-3-sonnet`, `claude-3-5-sonnet`, `claude-3-7-sonnet` -> `claude-sonnet-4-6`.
    - **Groq stable-first (2026)**
    - `groq-llama-3.3`, `groq-llama-3.1-8b`, `groq-gpt-oss-120b`, `groq-gpt-oss-20b`.
    - **Groq preview (optional)**
    - `groq-llama-4-scout-preview`.
    - **Groq legacy aliases**
    - `groq-mixtral`, `groq-llama2`, `groq-gemma` are remapped to modern Groq models.
    - **DeepSeek**
    - `deepseek-chat`, `deepseek-reasoner`, with `deepseek-coder` remapped to `deepseek-chat`.
    - **NVIDIA (OpenAI-compatible API)**
    - `nvidia-nemotron` -> `nvidia/nemotron-3-super-120b-a12b`.
    - **Z AI (OpenAI-compatible API)**
    - `z-ai-glm-5` -> `glm-5`.
    - **OpenRouter (OpenAI-compatible API)**
    - `openrouter-free` -> `openrouter/free`
    - `openrouter-qwen3-coder` -> `qwen/qwen3-coder:free`
    - `openrouter-claude-opus-4-6` -> `anthropic/claude-opus-4.6`
    - `openrouter-mimo-v2-pro` -> `xiaomi/mimo-v2-pro`
    - `openrouter-gpt-5-4` -> `openai/gpt-5.4`
    - `openrouter-deepseek-v3-2` -> `deepseek/deepseek-v3.2`
    - `openrouter-qwen3-coder-480b-free` -> `qwen/qwen3-coder-480b:free`
    - `openrouter-mimo-v2-flash-free` -> `xiaomi/mimo-v2-flash:free`
    - `openrouter-nemotron-3-super-free` -> `nvidia/nemotron-3-super:free`
    - `openrouter-minimax-m2-5-free` -> `minimax/minimax-m2.5:free`
    - `openrouter-qwen3-6-plus-free` -> `qwen/qwen3.6-plus:free`
    - **Browser Use**
    - `browser-use-bu-max` -> `bu-max` (session-based model).
    - **Hugging Face + local**
    - `hf-meta-llama-3`, `code-llama`, `code-llama-phind`, `mistral-7b`, `wizard-coder`, `star-chat`, `local-model`.

- Basic usage (with least options)</br>
```python
python interpreter.py
```
- `python interpreter.py` now opens the TUI and uses arrow-key navigation in a real terminal.
- The TUI falls back to plain text prompts when stdin is piped or not attached to a terminal.
- In `--tui` sessions, `/mode`, `/model`, `/language`, and `/settings` can reopen interactive selectors from inside the live chat interface.

- Launch the classic prompt-based CLI directly</br>
```python
python interpreter.py --cli -m 'z-ai-glm-5' -md 'code'
```
- `python interpreter.py --cli` automatically picks the best configured model from your `.env` file if you do not pass `-m`.
- Safe sandbox protections are enabled by default in `v3.0.0`.
- Use `--unsafe` only when you explicitly want to bypass the execution safety policy.
- LLM request retries are bounded to a maximum of `3` transient retry attempts before the final error is shown.

- Launch the selector-based TUI</br>
```python
python interpreter.py --tui
```

- Using different models (replace 'model-name' with your chosen model) </br>
```python
python interpreter.py --cli -md 'code' -m 'model-name' -dc
```

- Using different modes (replace 'mode-name' with your chosen mode) </br>
```python
python interpreter.py --cli -m 'model-name' -md 'mode-name'
```

- Using auto execution </br>
```python
python interpreter.py -m 'wizard-coder' -md 'code' -dc -e
```

- Saving the code </br>
```python
python interpreter.py -m 'code-llama' -md 'code' -s
```

- Selecting a language (replace 'language-name' with your chosen language) </br>
```python
python interpreter.py -m 'gemini-pro' -md 'code' -s -l 'language-name'
```

- Switching to File mode for prompt input (Here providing filename is optional) </br>
```python
python interpreter.py -m 'gemini-pro' -md 'code' --file 'my_prompt_file.txt'
```

- Using Upgrade interpreter </br>
```python
python interpreter.py --upgrade
```

- Live CLI smoke validation (stable models only) </br>
```bash
python scripts/validate_models_cli.py --providers gemini,groq --tier stable --mode chat
python scripts/validate_models_cli.py --providers openai,anthropic,deepseek,huggingface --tier stable --mode chat
python scripts/validate_models_cli.py --providers nvidia,z-ai,browser-use,openrouter --tier stable --mode chat
```

- Direct provider examples </br>
```bash
python interpreter.py -m 'nvidia-nemotron' -md 'chat' -dc
python interpreter.py -m 'z-ai-glm-5' -md 'chat' -dc
python interpreter.py -m 'openrouter-free' -md 'chat' -dc
python interpreter.py -m 'openrouter-qwen3-coder' -md 'chat' -dc
python interpreter.py -m 'browser-use-bu-max' -md 'chat' -dc
```

Last verified model baseline: **April 5, 2026**.

# Interpreter Commands 🖥️

Here are the available commands:

- 📝 `/save` - Save the last code generated.
- ✏️ `/edit` - Edit the last code generated.
- ▶️ `/execute` - Execute the last code generated.
- 🔄 `/mode` - Change the mode of interpreter.
- 🔄 `/model` - Change the model of interpreter.
- 📦 `/install` - Install a package from npm or pip.
- 🌐 `/language` - Change the language of the interpreter.
- 🧹 `/clear` - Clear the screen.
- 🆘 `/help` - Display this help message.
- 🚪 `/list` - List all the _models/modes/language_ available.
- 📝 `/version` - Display the version of the interpreter.
- 🚪 `/exit` - Exit the interpreter.
- 🐞 `/fix` - Fix the generated code for errors.
- ⚙️ `/settings` - Open interactive TUI settings when running with `--tui`.
- 📜 `/log` - Toggle different modes of logging.
- ⏫ `/upgrade` - Upgrade the interpreter.
- 📁 `/prompt` - Switch the prompt mode _File or Input_ modes.
- 💻 `/shell` - Access the shell.
- 🐞 `/debug` - Toggle Debug mode for debugging.


## ⚙️ **Settings**
You can customize the settings of the current model from the `.config` file. It contains all the necessary parameters such as `temperature`, `max_tokens`, and more.

### **Steps to add your own custom API Server**
To integrate your own API server for OpenAI instead of the default server, follow these steps:
1. Navigate to the `Configs` directory.
2. Open the configuration file for the model you want to modify. This could be either `gpt-3.5-turbo.config` or `gpt-4.config`.
3. Add the following line at the end of the file:
   ```
   api_base = https://my-custom-base.com
   ```
   Replace `https://my-custom-base.com` with the URL of your custom API server.
4. Save and close the file.
Now, whenever you select the `gpt-3.5-turbo` or `gpt-4` model, the system will automatically use your custom server.

## **Steps to add new models**

### **Manual Method**
1. 📋 Copy the `.config` file and rename it to `configs/hf-model-new.config`.
2. 🛠️ Modify the parameters of the model like `start_sep`, `end_sep`, `skip_first_line`.
3. 📝 Set the model name from Hugging Face to `HF_MODEL = 'Model name here'`.
4. 🚀 Now, you can use it like this: `python interpreter.py -m 'hf-model-new' -md 'code' -e`.
5. 📁 Make sure the `-m 'hf-model-new'` matches the config file inside the `configs` folder.

### **Automatic Method**
1. 🚀 Go to the `scripts` directory and run the `config_builder` script .
2. 🔧 For Linux/MacOS, run `config_builder.sh` and for Windows, run `config_builder.bat` .
3. 📝 Follow the instructions and enter the model name and parameters.
4. 📋 The script will automatically create the `.config` file for you.

## Star History

<a href="https://star-history.com/#haseeb-heaven/open-code-interpreter&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date" />
  </picture>
</a>

## 🤝 **Contributing**

If you're interested in contributing to **Code-Interpreter**, we'd love to have you! Please fork the repository and submit a pull request. We welcome all contributions and are always eager to hear your feedback and suggestions for improvements.

## 📌 **Versioning**

🚀 **v1.0** - Initial release.  
📊 **v1.1** - Added **Graphs** and **Charts** support.  
🔥 **v1.2** - Added **LiteLLM** Support.  
🌟 **v1.3** - Added **GPT 3.5** Support.  
🌴 **v1.4** - Added **PALM 2** Support.  
🎉 **v1.5** - Added **GPT 3.5/4** models official Support.  
📝 **v1.6** - Updated Code Interpreter for Documents files (**JSON**, **CSV**, **XML**).  
🌴 **v1.7** - Added **Gemini Pro Vision** Support for Image Processing.  

🌟 **v1.8** - Added **Interpreter Commands Support**:  

- 1.8.1 - Added _Interpreter Commands Debugging Support_.  
- 1.8.2 - Fixed _Interpreter Commands_  
- 1.8.3 - Added _Interpreter Commands Upgrade and Shell Support_.  
- 1.8.4 - Fixed _Interpreter Model switcher Bug_.  

🗨️ **v1.9** - Added new **Chat mode** 🗨️ for Chatting with your **Files**, **Data** and more.  

- v1.9.1 - Fixed _Unit Tests_ and _History Args_  
- v1.9.2 - Updated _Google Vision_ to adapt LiteLLM instead of _Google GenAI_.  
- v1.9.3 - Added **Local Models** Support via **LM Studio**.  

🔥 **v2.0** - Added **Groq-AI** Models _Fastest LLM_ with **500 Tokens/Sec** with _Code-LLaMa, Mixtral_ models.  

- **v2.0.1** - Added AnthropicAI Claude-2, Instant models.

🔥 **v2.1** - Added AnhtorpicAI Claude-3 models powerful _Opus,Sonnet,Haiku_ models.
- **v2.1.1** - Added **Groq-AI** Model _Gemma-7B_ with **700 Tokens/Sec**.
- **v2.1.2** - Added **Prompt Modes** now you can set prompt from file as well just place your prompt in `prompt.txt` file inside `system` directory.
- **v2.1.3** - Updated **OS Type detection** now for Linux **Arch & Debian** and generate accurate commands for all OS types.
- **v2.1.4** - Added **GPT-4o** models they are most effecient and cost effective models from **OpenAI**
- **v2.1.5** - Fixed OS type detection **Bug** for MacOS and feautre to open file with default editor.

🔥 **v2.2** - Save/Execute _commands_ and _scripts_, Fixed **Logging** and **Package Manager**.
- **Save/Execute**: Added support to **save and execute code, commands, and scripts** directly to external files.
- **Updated Commands**: 
  - Removed the `/debug` command and replaced it with the `/fix` command.
  - `/debug` command now handles application debugging and issue resolution effectively.
- **Improved Logger**:
  - Fixed issues with logging to both **files and console** simultaneously.
- **Dependency Management**:
  - Resolved pip package installation issues for smoother and more reliable setup.
- **v2.2.1** - Fixed **No Content/Response from LLM** Bug, Fixed _Debug Mode_ with **Logs**.

- **v2.3.0** - Added Deepseek V3 and R1 models support now. Added OpenAI o1 Models support.
- **v2.4.0** - 2026 model refresh: stable-first OpenAI/Gemini/Anthropic/Groq/DeepSeek catalog updates, legacy alias remaps, CLI smoke validator, and expanded unit tests.
- **v2.4.1** - Removed deprecated PALM model path, added NVIDIA + Z AI + Browser Use providers, added `.env.example`, cleaned project artifacts, and introduced `--cli` / `--tui` startup flows with safer interactive error handling.
- **v3.0.0** - Added a default execution safety sandbox, dangerous command/code circuit breaker, bounded ReACT-style repair retries after failures, clearer execution feedback, and polished CLI/TUI runtime output.

---

## 📜 **License**

This project is licensed under the **MIT License**. For more details, please refer to the LICENSE file.

Please note the following additional licensing details:

- The **GPT 3.5/4 models** are provided by **OpenAI** and are governed by their own licensing terms. Please ensure you have read and agreed to their terms before using these models. More information can be found at [OpenAI's Terms of Use](https://openai.com/policies/terms-of-use).

- The **Hugging Face models** are provided by **Hugging Face Inc.** and are governed by their own licensing terms. Please ensure you have read and agreed to their terms before using these models. More information can be found at [Hugging Face's Terms of Service](https://huggingface.co/terms-of-service).

- The **Anthropic AI models** are provided by **Anthropic AI** and are governed by their own licensing terms. Please ensure you have read and agreed to their terms before using these models. More information can be found at [Anthropic AI's Terms of Service](https://www.anthropic.com/terms).

## 🙏 **Acknowledgments**

- We would like to express our gratitude to **HuggingFace**,**Google**,**META**,**OpenAI**,**GroqAI**,**AnthropicAI** for providing the models.
- A special shout-out to the open-source community. Your continuous support and contributions are invaluable to us.

## **📝 Author**
This project is created and maintained by [Haseeb-Heaven](www.github.com/haseeb-heaven).
