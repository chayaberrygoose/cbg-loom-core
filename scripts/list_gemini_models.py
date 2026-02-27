
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("gemini_api_key")
genai.configure(api_key=api_key)

print("[SYSTEM_LOG]: Listing available models...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"{m.name}: {m.supported_generation_methods}")
