import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # For DeepSeek or Custom endpoint
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")

config = Config()
