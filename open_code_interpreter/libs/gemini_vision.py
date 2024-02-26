import os
from dotenv import load_dotenv
from open_code_interpreter.libs.logger import Logger
import litellm

class GeminiVision:
    def __init__(self, api_key=None) -> None:
        self.logger = Logger.initialize_logger('logs/vision_interpreter.log')
        self.logger.info(f"Initializing Gemini Vision")
        self.api_key = api_key
        
        if self.api_key is None:
            self.logger.warning("API key is not initialized")

            # load the key from the .env file
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self.logger.error("No API key found in the .env file")
                raise ValueError("No API key found in the .env file")
        
        self.logger.info(f"Gemini Vision configured success")
        self.logger.info(f"Model setup success")

    def generate_text(self, prompt, image_url):
        self.logger.info(f"Generating contents")
        
        # Create the messages payload according to the documentation
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    }
                ]
            }
        ]

        # Make the API call to Gemini model
        response = litellm.completion(
            model="gemini/gemini-pro-vision",
            messages=messages,
        )

        # Extract the response content
        return response.get('choices', [{}])[0].get('message', {}).get('content')

    def gemini_vision_url(self, prompt, image_url):
        self.logger.info(f"Generating text from URL: {image_url}")
        try:
            return self.generate_text(prompt, image_url)
        except Exception as exception:
            self.logger.error(f"Error generating text from URL: {exception}")
            raise

    def gemini_vision_path(self, prompt, image_path):
        self.logger.info(f"Generating text from image path: '{image_path}'")
        try:
            self.logger.info(f"Checking if image path exists for: '{image_path}'")
            
            # check if the image path exists
            if not os.path.exists(image_path):
                raise ValueError(f"Image path does not exist: {image_path}")
            
            return self.generate_text(prompt,image_path)
        except Exception as exception:
            self.logger.error(f"Error generating text from image path: {exception}")
            raise