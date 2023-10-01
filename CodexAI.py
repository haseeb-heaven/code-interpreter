import os
import openai

def get_country_capital_dict():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    prompt = "# Create a Python dictionary of 6 countries and their capitals\ncountries ="
    try:
        response = openai.Completion.create(
            model="code-davinci-001",
            prompt=prompt,
            temperature=0,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        if response.choices[0].text:
            output = response.choices[0].text.strip().split("=")[1]
            country_capital_dict = eval(output)
            return country_capital_dict
        else:
            raise Exception("No response received from OpenAI API")
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def main():
    country_capital_dict = get_country_capital_dict()
    if country_capital_dict:
        print(f"Country Capital Dictionary: {country_capital_dict}")
    else:
        print("Unable to retrieve country capital dictionary")

if __name__ == "__main__":
    main()
