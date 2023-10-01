import traceback
import requests
import logging
import os
import random
import dotenv

API_URL = "https://api-inference.huggingface.co/models/WizardLM/WizardCoder-Python-34B-V1.0"
#API_URL = "https://api-inference.huggingface.co/models/gpt2"
#API_URL = "https://api-inference.huggingface.co/models/codellama/CodeLlama-7b-hf"

# Setting the logger
logger = logging.getLogger(__name__)

def send_query(payload,headers):
    logger.info("Trying to send query to server... ")
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        logger.info("Query sent successfully")
    return response.json()

def query_builder(input, temperature=0.3, max_length=500, min_length=128, max_new_tokens=250):
    quuery = {
        "inputs": input,
        "parameters": {
            "temperature": temperature,
            "max_length": max_length,
            "min_length": min_length,
            "max_new_tokens": max_new_tokens,
        },
        "options": {
            "use_cache": True,
            "wait_for_model": True,
        }
    }
    logger.info(f"Query: {quuery}")
    return quuery


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

# Create logger with file handler only with formatted timestamp.
def get_logger(file_name='VICI.log') -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(file_name)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def read_config_file():
    with open(".config", "r") as f:
        config_text = f.read()

    config_values = {}
    for line in config_text.split("\n"):
        if line.strip() != "":
            key, value = line.split("=")
            config_values[key.strip()] = value.strip()

    temperature = float(config_values["temperature"])
    max_length = int(config_values["max_length"])
    min_length = int(config_values["min_length"])
    max_new_tokens = int(config_values["max_new_tokens"])
    return temperature, max_length, min_length, max_new_tokens

def main():
    # Hugging Face Inferencing API
    
    # load the hugging face API token from .env file
    dotenv.load_dotenv()
    
    # Setting logger and hugging face token.
    logger = get_logger('VICI.log')
    hugging_face_token = os.getenv("HUGGING_FACE_TOKEN")
    
    # read the model config from .config file
    temperature, max_length, min_length, max_new_tokens = read_config_file()
    
    # log configuration information
    logger.info("VICI Model Config")
    logger.info(f"Temparature: {temperature}")
    logger.info(f"Max Length: {max_length}")
    logger.info(f"Min Length: {min_length}")
    logger.info(f"Max New Tokens: {max_new_tokens}\n")
    
    # Set the token to the header
    headers = {"Authorization": "Bearer " + hugging_face_token}
    
    # extract the text find the last / in API_URL and extract the model name
    model_name = API_URL.split("/")[-1]
    print("Welcome - VICI AI @" + model_name)
    prompt = input("Enter your prompt: ")
    
    # generate random number for filename
    random_number = random.randint(1, 1000)
    
    try:
        # save the prompts to a file
        save_prompts(prompt,random_number)
        
        query = query_builder(prompt,temperature,max_length,min_length,max_new_tokens)
        output = send_query(query,headers)
              
        if output and output.__len__() > 0:
            logger.info(f"Output: {output}")
            output = output[0]['generated_text']
            output_text = output.split("\end{code}")[0][1:]
            print(output_text)
            #print(output)
            # save the output to a file
            save_output(output,random_number)
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error occurred: {e}")
        logger.error(f"Stack Trace: {stack_trace}")

def run_app():
    while True:
        main()
        user_input = input("Press 'q' to quit the app, or any other key to continue: ")
        if user_input.lower() == 'q':
            break

if __name__ == '__main__':
    print("Running VICI AI...")
    # run the main function once to test the API 
    run_app()
    print("Exiting VICI AI...")

