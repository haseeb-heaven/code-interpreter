import subprocess
import time
from huggingface_hub import InferenceClient
import random
import logging
from libs.markdown_code import display_code, display_code_stream
from libs.chat_coder_llm import ChatCoderLLM

API_URL = "https://api-inference.huggingface.co/models/"
client = InferenceClient(
    "mistralai/Mistral-7B-Instruct-v0.1"
)

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
def format_prompt(message, history):
  prompt = "<s>"
  for user_prompt, bot_response in history:
    prompt += f"[INST] {user_prompt} [/INST]"
    prompt += f" {bot_response} "
  prompt += f"[INST] {message} [/INST]"
  return prompt

def generate(prompt, history, temperature=0.9, max_new_tokens=512, top_p=0.95, repetition_penalty=1.0):
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

    formatted_prompt = format_prompt(prompt, history)

    stream = client.text_generation(formatted_prompt, **generate_kwargs, stream=True, details=True, return_full_text=False)
    return stream

def extract_code_from_stream(stream):
    try:
        code = ""
        for output in stream:
            code += output.token.text
    except Exception as exception:
        logger.error(f"Error occurred while extracting code from stream: {exception}")
        raise
    return code


def main():
    history = []
    print("Mistral Chat - v 1.0")
    chat_coder_llm = ChatCoderLLM()
    
    while True:
        try:
            # Define the task
            task = input("> ")
            if task.lower() in ['exit', 'quit']:
                print("Exiting Mistral Chat.")
                break

            # Define the specifications
            specifications = [
                "You are code interpreter and can do and solve tasks using Python language so whatever user ask just try to solve that using Python code",
                "Write Code in Python and dont add a main method.",
                "Code should be sequential",
                "The output should only contain the code.",
                "The code should not have any comments.",
                "The code should not ask for any input.",
                "The output should not contain any text or explanations",
            ]

            # Combine the task and specifications into a single prompt
            prompt = task + " " + " ".join(specifications)
        
            #logger.info(f"Prompt: {prompt}")
            code = []
            stream = list(generate(prompt, history, temperature=0.1, max_new_tokens=4096))
            display_code_stream(stream)
            
            code = extract_code_from_stream(stream)
            #logger.info(f"Code: {code}")
            
            extracted_code = chat_coder_llm.extract_code(code)
            #logger.info(f"Extracted code: {extracted_code}")
            
            # Save the extracted code in file
            chat_coder_llm.save_code(code=extracted_code)
            
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
            print(f"Error: {exception}")

if __name__ == "__main__":
    main()

