import os
from dotenv import load_dotenv
from libs.logger import Logger
from PIL import Image
import io
import requests
from litellm import litellm

class GeminiVision:
    def __init__(self,api_key=None,temperature=0.1,top_p=1,top_k=32,max_output_tokens=13000) -> None:
        self.logger = Logger.initialize_logger('logs/vision_interpreter.log')
        self.logger.info(f"Initializing Gemini Vision")
        self.api_key = api_key
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens
        
        self.logger.info(f"temperature: {self.temperature}")
        self.logger.info(f"top_p: {self.top_p}")
        self.logger.info(f"top_k: {self.top_k}")
        self.logger.info(f"max_output_tokens: {self.max_output_tokens}")
        
        if self.api_key is None:
            self.logger.error("API key is not initialized")

            # load the key from the .env file
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self.logger.error("No API key found in the .env file")
                raise ValueError("No API key found in the .env file")
        
        self.logger.info(f"Gemini Vision configured success")
        
    def _generate_message(self,prompt, image_url):
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]

    def _get_content_from_response(self,response):
        try:
            return response['choices'][0]['message']['content']
        except (KeyError, IndexError) as e:
            self.logger.error(f"Invalid response structure: {e}")
            return None

    def generate_text(self,prompt, image_url):
        try:
            messages = self._generate_message(prompt, image_url)
            response = litellm.completion(model="gemini/gemini-pro-vision", messages=messages,temperature=self.temperature,max_output_tokens=self.max_output_tokens,top_p=self.top_p,top_k=self.top_k)
            content = self._get_content_from_response(response)
            if content:
                self.logger.info("Content found from Gemini Vision")
                return content
            else:
                self.logger.warning("No content found in the response")
        except Exception as exception:
            self.logger.error(f"An error occurred while generating text: {exception}")
            raise
    
    def _get_image_from_url(self, image_url):
        self.logger.info(f"Getting image from URL: {image_url}")
        try:
            response = requests.get(image_url)
            response.raise_for_status() # Raise an exception if the request failed
            image = Image.open(io.BytesIO(response.content))
            return image
        except Exception as exception:
            self.logger.error(f"Error getting image from URL: {exception}")
            raise

    def gemini_vision_url(self, prompt, image_url):
        self.logger.info(f"Generating text from URL: {image_url}")
        try:
            response = self.generate_text(prompt, image_url)
    
            if 'error' in response:
                raise ValueError(f"An error occurred: {response}")
            else:
                if response:
                    self.logger.info(f"Response: {response}")
                    return response
        except Exception as exception:
            self.logger.error(f"Error generating text from URL: {exception}")
            raise

    def gemini_vision_path(self, prompt, image_path):
        self.logger.info(f"Generating text from image path: '{image_path}'")
        try:
            self.logger.warning(f"LiteLLM does not support image paths yet")
            raise NotImplementedError(f"LiteLLM does not support image paths yet")
        
            self.logger.info(f"Checking if image path exists for: '{image_path}'")
            
            if not image_path:
                raise ValueError(f"Image path is not initialized")
            
            # check if the image path exists
            if not os.path.exists(image_path):
                raise ValueError(f"Image path does not exist: {image_path}")
            
            # Open the image
            image = Image.open(image_path)
            contents = [prompt, image]

            self.logger.info(f"Contents: {contents}")
            response = self.generate_text(prompt, image_path)

            if 'error' in response:
                raise ValueError(f"An error occurred: {response}")
            else:
                if response.text:
                    self.logger.info(f"Response: {response.text}")
                    return response.text
        except Exception as exception:
            self.logger.error(f"Error generating text from image path: {exception}")
            raise