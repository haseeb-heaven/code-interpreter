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
You are a helpful, respectful and honest assistant with a deep knowledge of code and software design. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content.Please ensure that your responses are socially unbiased and positive in nature.\n\nIf a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.\
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
    if temperature < 1e-2:
        temperature = 1e-2
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


def extract_code_from_stream(stream):
    try:
        output = ""
        for response in stream:
            if any([end_token in response.token.text for end_token in [EOS_STRING, EOT_STRING]]):
                return output
            else:
                output += response.token.text
            yield output
        return output
    except Exception as exception:
        logger.error(f"Error occurred while extracting code from stream: {exception}")
        raise
    return code

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
    
            # Define the specifications
            specifications = [
                "You are code interpreter and can do and solve tasks",
                "Write Code in Python and dont add a main method.",
                "Code should be sequential",
                "The output should only contain the code.",
                "The code should not have any comments.",
                "The code should not ask for any input.",
                "The output should not contain any text or explanations",
            ]

            # Combine the task and specifications into a single prompt
            prompt = "Now write Python code for this task '" + task #+ "' " + " ".join(specifications)
            logger.debug(f"Prompt: {prompt}")
                    
            output = generate_text(prompt,history,temperature=0.1,max_new_tokens=256)
            code_output = display_code_stream(output)
            print(f"code_output is {code_output}")
            
            extract_code = extract_code_from_stream(output)
            print(f"extract_code is {extract_code}")

            start_code_separator = "begin{code}"
            end_code_separator = 'end{code}'
            extracted_code = chat_coder_llm.extract_code(code_output,start_sep=start_code_separator,end_sep=end_code_separator)
            logger.debug(f"extracted_code is {extracted_code}")
            
            if extracted_code:
                # Ask for user confirmation before executing the extracted code
                execute = input("Do you want to execute the extracted code? (Y/N): ")
                if execute.lower() == 'y':
                    try:
                        output = chat_coder_llm.execute_code(extracted_code,language='python')
                        logger.info(f"Output: {output}")
                    except Exception as exception:
                        raise exception
        except Exception as exception:
            logger.error(f"Error: {exception}")
    
if __name__ == "__main__":
    main()
