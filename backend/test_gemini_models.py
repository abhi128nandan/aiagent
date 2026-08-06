import os
import requests
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print("Fetching available Gemini models...")
response = requests.get(url)
if response.status_code == 200:
    models = response.json().get("models", [])
    for m in models:
        print(f"Name: {m.get('name')} | Supported methods: {m.get('supportedGenerationMethods')}")
else:
    print(f"Failed to fetch: {response.status_code} - {response.text}")
