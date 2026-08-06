import asyncio
import os
from litellm import completion
from dotenv import load_dotenv
load_dotenv()

async def test_groq():
    try:
        print("Testing Groq connection via LiteLLM...")
        model = "groq/llama-3.3-70b-versatile"
        api_key = os.getenv("GROQ_API_KEY")
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

asyncio.run(test_groq())
