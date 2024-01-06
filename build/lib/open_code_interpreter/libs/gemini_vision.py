import os
import google.generativeai as genai
from dotenv import load_dotenv
from open_code_interpreter.libs.logger import initialize_logger
from PIL import Image
import io
import requests

class GeminiVision:
    def __init__(self,api_key=None,temperature=0.1,top_p=1,top_k=32,max_output_tokens=4096) -> None:
        self.logger = initialize_logger('logs/vision_interpreter.log')
        self.logger.info(f"Initializing Gemini Vision")
        self.model = None
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
        genai.configure(api_key=api_key)
        
        self.logger.info(f"Setting up model")
        self.setup_model()
        self.logger.info(f"Model setup success")

    def setup_model(self):
        try:
            # Set up the model
            generation_config = {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "max_output_tokens": self.max_output_tokens,
            }

            self.model = genai.GenerativeModel(model_name="gemini-pro-vision",generation_config=generation_config)
        except Exception as exception:
            self.logger.error(f"Error setting up model: {exception}")
            raise

    def generate_content(self, contents):
        self.logger.info(f"Generating contents")
        
        # Check model and contents for errors.
        if self.model is None:
            self.logger.error("Model is not initialized")
            raise ValueError("Model is not initialized")

        if contents is None:
            self.logger.error("Contents is not initialized")
            raise ValueError("Contents is not initialized")
        
        # Print out the contents list for debugging
        self.logger.info(f"Contents: {contents}")
        
        return self.model.generate_content(contents=contents)
    
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
            image = self._get_image_from_url(image_url)
            contents = [prompt, image]
            self.logger.info(f"Contents: {contents}")
            response = self.generate_content(contents=contents)
    
            if 'error' in response:
                raise ValueError(f"An error occurred: {response}")
            else:
                if response.text:
                    self.logger.info(f"Response: {response.text}")
                    return response.text
        except Exception as exception:
            self.logger.error(f"Error generating text from URL: {exception}")
            raise

    def gemini_vision_path(self, prompt, image_path):
        self.logger.info(f"Generating text from image path: '{image_path}'")
        try:
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
            response = self.generate_content(contents=contents)

            if 'error' in response:
                raise ValueError(f"An error occurred: {response}")
            else:
                if response.text:
                    self.logger.info(f"Response: {response.text}")
                    return response.text
        except Exception as exception:
            self.logger.error(f"Error generating text from image path: {exception}")
            raise