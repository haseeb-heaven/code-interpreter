import requests
import logging
import random
import json
from libs.chat_coder_llm import ChatCoderLLM
from huggingface_hub import InferenceClient

from libs.markdown_code import display_code_stream
EOS_STRING = "</s>"
EOT_STRING = "<EOT>"

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

client = InferenceClient(
    "codellama/CodeLlama-34b-Instruct-hf"
)

DEFAULT_SYSTEM_PROMPT = """\
As 'LLama-Interpreter', your role is to generate Python code. The code you produce should adhere to the following guidelines:
- It should be sequential with main method included: The code should follow a linear, step-by-step progression.
- It should be devoid of comments: To maintain clarity, avoid adding comments within the code.
- It should not ask for user input: The code should be able to run independently without requiring any input during its execution.
- It should not contain explanations or additional text: The output should strictly be Python code, free from any supplementary text or explanations.
Remember, the goal is to provide clear, concise, and safe code solutions.\
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
    
    stream = client.text_generation(prompt, **generate_kwargs, stream=True, details=True, return_full_text=False)
    #logger.debug(f"Generated code {stream}")
    return stream

def extract_text_stream(stream):
    output = ""
    try:
        for response in stream:
            if any([end_token in response.token.text for end_token in [EOS_STRING, EOT_STRING]]):
                logger.debug("End token found in response. Returning output.")
                return output
            else:
                output += response.token.text
                logger.debug(f"Current output: {output}")
    except Exception as e:
        logger.error(f"Error occurred while extracting text stream: {e}")
        raise e
    logger.debug(f"Extracted text stream: {output}")
    return output

def main():
    history = []
    print("CodeLlama Chat - v 1.0")
    chat_coder_llm = ChatCoderLLM()
    
    while True:
        try:
            # Define the task
            task = input("> ")
            if task.lower() in ['exit', 'quit']:
                print("Exiting CodeLlama Chat.")
                break
    
            # Combine the task and specifications into a single prompt
            prompt = f"Create a Python code for this task '{task}'"
            logger.debug(f"Prompt: {prompt}")
                    
            stream = generate_text(prompt,history,temperature=0.1,max_new_tokens=1024)
            extracted_code = display_code_stream(stream)
            
            #extracted_code = extract_text_stream(stream)
            
            if extracted_code:
                if not chat_coder_llm.is_python_code(extracted_code):
                    logger.warning("The extracted code is not valid Python code.")
                    
                # Ask for user confirmation before executing the extracted code
                execute = input("Do you want to execute the extracted code? (Y/N): ")
                if execute.lower() == 'y':
                    try:
                        python_code = chat_coder_llm.extract_python_code(extracted_code)
                        chat_coder_llm.save_code(code=python_code)
                        stream = chat_coder_llm.execute_code(python_code,language='python')
                        logger.info(f"Output: {stream}")
                    except Exception as exception:
                        raise exception
        except Exception as exception:
            logger.error(f"Error: {exception}")
    
if __name__ == "__main__":
    main()
