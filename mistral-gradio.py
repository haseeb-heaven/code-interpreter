import subprocess
import time
from huggingface_hub import InferenceClient
import random
import logging
from markdown_code import display_code, display_code_stream
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
    return stream

def main():
    history = []
    print("Mistral Chat - v 1.0")
    while True:
        try:
            # Define the task
            task = "Show me all prime numbers from 30 to 66" 

            # Define the specifications
            specifications = [
                "Write Code in Python and dont add a main method.",
                "Code should be sequential",
                "The output should only contain the code.",
                "The code should not have any comments.",
                "The code should not ask for any input.",
                "The output should not contain any text or explanations",
            ]

            # Combine the task and specifications into a single prompt
            prompt = task + " " + " ".join(specifications)
        
            logger.info(f"Prompt: {prompt}")
            code = []
            stream = generate(prompt, history, temperature=0.1, max_new_tokens=1024)
            display_code_stream(stream)
            break
        except Exception as exception:
            print(f"Error: {exception}")

if __name__ == "__main__":
    main()

