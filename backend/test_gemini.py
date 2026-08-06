import asyncio
import os
import sys
from litellm import completion

# Load env
from dotenv import load_dotenv
load_dotenv()

async def test_gemini():
    try:
        print("Testing Gemini connection via LiteLLM...")
        model = "gemini/gemini-flash-latest"
        api_key = os.getenv("GEMINI_API_KEY")
        print(f"Model: {model}")
        print(f"Key preview: {api_key[:6]}...{api_key[-4:]}" if api_key else "None")
        
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Say hello"}],
            api_key=api_key
        )
        print("SUCCESS:", response.choices[0].message.content)
    except Exception as e:
        print("ERROR:", str(e))
        import traceback
        traceback.print_exc()

asyncio.run(test_gemini())
