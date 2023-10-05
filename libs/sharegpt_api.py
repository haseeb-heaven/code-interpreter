"""
Description: This file contains methods to post conversation data to ShareGPT API and get ShareGPT URL.
Link : https://github.com/domeccleston/sharegpt#rest-api
Author of ShareGPT : Dome Eccleston
"""
import json
import requests

url = "https://sharegpt.com/api/conversations"

# Method to post conversation data to ShareGPT API    
def sharegpt_post_conversation(conversation_data):
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(conversation_data))
    response_data = response.json()
    id = response_data["id"]
    sharegpt_url = f"https://shareg.pt/{id}"
    return sharegpt_url

# Method to get ShareGPT URL
def sharegpt_get_url(gpt_data="", human_data=""):
    conversation_data = {
        "items": [
            {"from": "gpt", "value": gpt_data},
            {"from": "human", "value": human_data},
        ]
    }
    sharegpt_url = sharegpt_post_conversation(conversation_data)
    return sharegpt_url