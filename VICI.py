import traceback
import requests
import logging
import os
import random
import dotenv

#API_URL = "https://api-inference.huggingface.co/models/WizardLM/WizardLM-70B-V1.0"
API_URL = "https://api-inference.huggingface.co/models/WizardLM/WizardCoder-Python-34B-V1.0"
#API_URL = "https://api-inference.huggingface.co/models/codeparrot/starcoder-self-instruct"
#API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-hf"


def send_query(payload,headers):
	response = requests.post(API_URL, headers=headers, json=payload)
	return response.json()

def query_builder(input, temperature=0.3, max_length=4096, min_length=128):
    return {
        "inputs": input,
        "parameters": {
            "temperature": temperature,
            "max_length": max_length,
            "min_length": min_length,
        },
        "options": {
            "use_cache": True,
            "wait_for_model": True,
        }
    }


def save_prompts(prompt_text,random_number):
    # create prompts directory if it doesn't exist
    if not os.path.exists("prompts"):
        os.makedirs("prompts")
    
    # write prompt text to file
    with open(f"prompts/prompt_{random_number}.txt", "w") as f:
        f.write(prompt_text)

def save_output(output_text,random_number):
    # create outputs directory if it doesn't exist
    if not os.path.exists("outputs"):
        os.makedirs("outputs")
    
    # write output text to file
    with open(f"outputs/output_{random_number}.txt", "w") as f:
        f.write(output_text)


def main():
    # Hugging Face Inferencing API
    # load the hugging face API token from .env file
    dotenv.load_dotenv()
    
    hugging_face_token = os.getenv("HUGGING_FACE_TOKEN")
    
    # Set the token to the header
    headers = {"Authorization": "Bearer " + hugging_face_token}
    
    print("Welcome - VICI AI")
    prompt = input("Enter your prompt: ")
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # generate random number for filename
    random_number = random.randint(1, 1000)
    
    try:
        # save the prompts to a file
        save_prompts(prompt,random_number)
        
        query = query_builder(prompt, temperature=0.1, max_length=4096, min_length=128)
        output = send_query(query,headers)
              
        if output and output.__len__() > 0:
            output = output[0]['generated_text']
            logging.info(f"Output: {output}")
            # save the output to a file
            save_output(output,random_number)
    except Exception as e:
        stack_trace = traceback.format_exc()
        logging.error(f"Error occurred: {e}")
        logging.error(f"Stack Trace: {stack_trace}")

if __name__ == '__main__':
    main()
