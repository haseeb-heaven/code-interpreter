import requests
import logging
import random
import json
from libs.chat_coder_llm import ChatCoderLLM
from huggingface_hub import InferenceClient

from libs.markdown_code import display_code, display_code_stream, display_markdown_message

# Initialize logger
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler(__file__.replace('.py','') + '.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

client = InferenceClient(
    "codellama/CodeLlama-34b-Instruct-hf"
)

DEFAULT_SYSTEM_PROMPT = """\
As 'LLama-Code-Generator', your sole role is to generate Python code. The code should:
- Be sequential with a main method included.
- Be devoid of comments.
- Not ask for user input.
- Not contain explanations or additional text.
- Not be modular.
Remember, you can only output Python code and nothing else you don't have ability to respond in plain text.
"""

def get_prompt(message: str, chat_history: list[tuple[str, str]],system_prompt: str) -> str:
    texts = [f'<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n']
    # The first user input is _not_ stripped
    do_strip = False
    for user_input, response in chat_history:
        user_input = user_input.strip() if do_strip else user_input
        do_strip = True
        texts.append(f'{user_input} [/INST] {response.strip()} </s><s>[INST] ')
    message = message.strip() if do_strip else message
    texts.append(f'{message} [/INST]')
    return ''.join(texts)

def generate_text(message,chat_history: list[tuple[str, str]], temperature=0.9, max_new_tokens=512, top_p=0.95, repetition_penalty=1.0):
    logger.debug("Generating code.")
    temperature = float(temperature)
    temperature = max(temperature, 0.01)
    top_p = float(top_p)

    generate_kwargs = dict(
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        do_sample=True,
        seed=random.randint(0, 10**7),
    )

    prompt = get_prompt(message, chat_history, DEFAULT_SYSTEM_PROMPT)
    
    stream = client.text_generation(prompt, **generate_kwargs, stream=False, details=True, return_full_text=False)
    logger.debug(f"Generated code {stream.generated_text}")
    return stream.generated_text

def get_os_platform():
    try:
        import platform
        os_info = platform.uname()
        os_name = os_info.system

        # Map the system attribute to the desired format
        os_name_mapping = {
            'Darwin': 'MacOS',
            'Linux': 'Linux',
            'Windows': 'Windows'
        }

        os_name = os_name_mapping.get(os_name, 'Other')

        logger.info(f"Operating System: {os_name} Version: {os_info.version}")
        return os_name, os_info.version
    except Exception as exception:
        logger.error(f"Error in checking OS and version: {str(exception)}")
        raise Exception(f"Error in checking OS and version: {str(exception)}")

def main():
    history = []
    CODE_INTERPRETER_LANGUAGE = 'javascript'
    
    print("CodeLlama Chat - v 1.0")
    chat_coder_llm = ChatCoderLLM()
    
    # Get the OS Platform and version.
    os_platform = get_os_platform()
    os_name = os_platform[0]
    os_version = os_platform[1]
    
    display_code(f"OS = {os_name}")
    display_code(f"language = {CODE_INTERPRETER_LANGUAGE}")
    
    while True:
        try:
            # Define the task
            task = input("> ")
            if task.lower() in ['exit', 'quit']:
                print("Exiting CodeLlama Chat.")
                break
    
            # Combine the task and specifications into a single prompt
            prompt = f"Generate the code in {CODE_INTERPRETER_LANGUAGE} programming language for this task '{task} for Operating System is {os_name}'."
            history.append((task,prompt))
            logger.debug(f"Prompt: {prompt}")
                    
            generated_output = generate_text(prompt,history,temperature=0.1,max_new_tokens=1024)
            logger.info(f"Generated output type {type(generated_output)}")
            
            extracted_code = chat_coder_llm.extract_code(generated_output)
            logger.info(f"Extracted code: {extracted_code[:50]}")
            display_code(extracted_code)
            
            if extracted_code:
                # Ask for user confirmation before executing the extracted code
                execute = input("Do you want to execute the extracted code? (Y/N): ")
                if execute.lower() == 'y':
                    try:
                        #python_code = chat_coder_llm.extract_python_code(extracted_code)
                        logger.info(f"Extracted {CODE_INTERPRETER_LANGUAGE} code: {extracted_code[:50]}")
                        chat_coder_llm.save_code("code_generated.js",extracted_code)
                        logger.info(f"Python code saved successfully.")
                        code_output,code_error = chat_coder_llm.execute_code(extracted_code,language=CODE_INTERPRETER_LANGUAGE)
                        if code_output and code_output != None and code_output.__len__() > 0:
                            logger.info(f"{CODE_INTERPRETER_LANGUAGE} code executed successfully.")
                            display_markdown_message(f"Output: {code_output}")
                        elif code_error:
                            logger.info(f"Python code executed with error.")
                            display_markdown_message(f"Error: {code_error}")
                            
                        logger.info(f"Output: {code_output}")
                    except Exception as exception:
                        raise exception
        except Exception as exception:
            # print the traceback
            import traceback
            traceback.print_exc()
            logger.error(f"Error occurred: {str(exception)}")
            raise exception
    
if __name__ == "__main__":
    main()
