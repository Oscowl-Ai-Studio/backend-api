import os

import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("OLLAMA_BASE_URL")

payload = {
    "model": "tinyllama",
    "prompt": "What is AI?",
    "stream": False
}

response = requests.post(url, json=payload)

print(response.json()["response"])