from langchain.prompts import PromptTemplate
from langchain import HuggingFaceHub, LLMChain 
from dotenv import load_dotenv

def read_config_file():
    try:
        
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
    except Exception as e:
        print(f"Error: {e}")
        return None, None, None, None
    return temperature, max_length, min_length, max_new_tokens


def main():
    try:
        load_dotenv()  # load the hugging face API token from .env file
        
        # read the model config from .config file
        temperature, max_length, min_length, max_new_tokens = read_config_file()
        #repo_id = "codellama/CodeLlama-7b-hf"
        repo_id = "codellama/CodeLlama-34b-Instruct-hf"
        
        hub_llm = HuggingFaceHub(
            repo_id=repo_id,
            model_kwargs={
                "temperature": temperature,
                "min_length": min_length,
                "max_length": max_length,
                "num_return_sequences": 1,
                "max_new_tokens":max_new_tokens,
            }
        )
        
        prompt = PromptTemplate(
            input_variables=['profession','job','code'],
            template= "You're {profession} and your job is {job} and code: {code}"
        )

        hub_chain = LLMChain(prompt=prompt, llm=hub_llm,verbose=True)
        
        input_code = "def factorial(number):"
        developer_output = hub_chain.run({"profession":"developer","job":"is provide the professional code well written code for ","code":input_code})
        developer_output = developer_output.strip() # strip the output
        # remove """ escape characters from 
        developer_output = developer_output.replace("\\n","").replace("\\t","").replace("\\","").replace("\"","").replace("\'","")
        coderunner_output = hub_chain.run({"profession":"runner","job":"is to add the main method with included with examples to load for the given code","code":developer_output})
        if not coderunner_output and coderunner_output.__len__() == 0:
            print("No output generated")
        else:
            with open("code.py", "w") as file:
                file.write(input_code + str(coderunner_output))
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
