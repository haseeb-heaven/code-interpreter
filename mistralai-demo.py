import random
import time
from huggingface_hub import InferenceClient
import logging
from markdown_code import display_code
API_URL = "https://api-inference.huggingface.co/models/"

client = InferenceClient(
    "mistralai/Mistral-7B-Instruct-v0.1"
)
# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def save_code(filename='code_generated.py', code=None):
    """
    Saves the provided code to a file.
    The default filename is 'code_generated.py'.
    """
    try:
        with open(filename, 'w') as file:
            file.write(code)
            logger.info(f"Code saved successfully to {filename}.")
    except Exception as exception:
        logger.error(f"Error occurred while saving code to file: {exception}")
        raise

def extract_code(code):
    """
    Extracts the code from the provided string.
    If the string contains '```', it extracts the code between them.
    Otherwise, it returns the original string.
    """
    try:
        if '```' in code:
            start = code.find('```') + len('```\n')
            end = code.find('```', start)
            # Skip the first line after ```
            start = code.find('\n', start) + 1
            extracted_code = code[start:end]
            logger.info("Code extracted successfully.")
            return extracted_code
        else:
            logger.info("No special characters found in the code. Returning the original code.")
            return code
    except Exception as exception:
        logger.error(f"Error occurred while extracting code: {exception}")
        return None

import subprocess

def execute_code(code):
    try:
        logger.info(f"Attempting to execute code {code}")
        process = subprocess.Popen(["python", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        stdout_output = stdout.decode("utf-8")
        stderr_output = stderr.decode("utf-8")
        logger.info(f"Code execution completed. Output: {stdout_output}, Errors: {stderr_output}")
        return stdout_output, stderr_output
    except Exception as exception:
        logger.error(f"Error occurred while executing code: {str(exception)}")
        raise


def format_prompt(message, history):
  prompt = "<s>"
  for user_prompt, bot_response in history:
    prompt += f"[INST] {user_prompt} [/INST]"
    prompt += f" {bot_response}</s> "
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
    output = ""

    for response in stream:
        output += response.token.text
        yield output
    return output

def main():
    try:
        # Define the task
        task = "Write a Python code for generate prime numbers from 1 to 100"

        # Define the specifications
        specifications = [
            "Include a main method.",
            "Code should be modular",
            "The output should only contain the code.",
            "The code should not have any comments.",
            "The code should not ask for any input."
        ]

        # Combine the task and specifications into a single prompt
        prompt = task + " " + " ".join(specifications)
        
        logger.info(f"Prompt: {prompt}")
        history = []
        output = generate(prompt, history)
        #logger.info(f"Output: {output}")
        for generated_text in generate(prompt, history):
            for char in generated_text:
                print(char, end='', flush=True)
        
        return
            
        if output:
            # Convert the generator object to a string
            code_str = '\n'.join(output)
            code = extract_code(code_str)
            logger.info(f"Code extracted successfully: {code}")
            if code:
                save_code(code=code)  # Save the extracted code before executing
                #output, stderr = execute_code(code_str)
                #logger.info(f"Code execution completed with output: {output} and stderr is {stderr}")
            else:
                logger.error("No code extracted from the output.")
        else:
            logger.error("No output received from the query.")
    except Exception as exception:
        logger.error(f"Error occurred in main: {str(exception)}")

if __name__ == "__main__":
	main()

